import os
import httpx
from typing import List, Dict, Any, Optional
import logging
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.ollama_host = os.getenv("OLLAMA_HOST", "localhost")
        self.ollama_port = os.getenv("OLLAMA_PORT", "11434")
        self.ollama_url = f"http://{self.ollama_host}:{self.ollama_port}"

    async def generate_response(
        self, question: str, collection_id: Optional[str] = None, debug: bool = False
    ) -> Dict[str, Any]:
        """Generate a response using RAG"""
        try:

            if collection_id:
                relevant_chunks = await self.vector_store.search(
                    collection_id, question, limit=5
                )
            else:

                collections = await self.vector_store.list_collections()
                if not collections:
                    return {
                        "response": "No documents have been uploaded yet. Please upload some documents first.",
                        "sources": [],
                    }
                collection_id = collections[0]["id"]
                relevant_chunks = await self.vector_store.search(
                    collection_id, question, limit=5
                )

            context = self._build_context(relevant_chunks)

            response, full_prompt = await self._generate_with_ollama(
                question, context, debug
            )

            sources = [
                chunk["metadata"].get("filename", "Unknown")
                for chunk in relevant_chunks
            ]
            sources = list(set(sources))

            result = {"response": response, "sources": sources}

            if debug:
                result["debug_info"] = {
                    "context": context,
                    "full_prompt": full_prompt,
                    "relevant_chunks": [
                        {
                            "content": chunk["content"],
                            "metadata": chunk["metadata"],
                            "score": chunk.get("score"),
                        }
                        for chunk in relevant_chunks
                    ],
                }

            return result

        except Exception as e:
            logger.error(f"Error generating RAG response: {e}")
            return {
                "response": f"Sorry, I encountered an error while processing your question: {str(e)}",
                "sources": [],
            }

    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Build context string from relevant document chunks"""
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            filename = chunk["metadata"].get("filename", "Unknown")
            content = chunk["content"]

            context_part = f"[Source {i} - {filename}]\n{content}\n"
            context_parts.append(context_part)

        return "\n".join(context_parts)

    async def _generate_with_ollama(
        self, question: str, context: str, debug: bool = False
    ) -> tuple[str, str]:
        """Generate response using Ollama"""
        prompt = f"""Based on the following context from uploaded documents, please answer the question.
If the answer cannot be found in the context, please say so clearly.

Context:
{context}

Question: {question}

Answer:"""

        try:
            async with httpx.AsyncClient() as client:

                await self._ensure_model_available(client)

                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": "qwen3:0.6b-q4_K_M",
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1},
                    },
                    timeout=180.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    response_text = result.get(
                        "response", "Sorry, I couldn't generate a response."
                    )
                    return response_text, prompt if debug else ""
                else:
                    logger.error(
                        f"Ollama API error: {response.status_code} - {response.text}"
                    )
                    error_response = (
                        "Sorry, I encountered an error while generating the response."
                    )
                    return error_response, prompt if debug else ""

        except httpx.ConnectError:
            error_response = "Sorry, the AI model service is not available. Please ensure Ollama is running."
            return error_response, prompt if debug else ""
        except Exception as e:
            logger.error(f"Error calling Ollama API: {e}")
            error_response = f"Sorry, there was an error: {str(e) or type(e).__name__ or 'Unknown error'}"
            return error_response, prompt if debug else ""

    async def _ensure_model_available(self, client: httpx.AsyncClient):
        """Ensure the required model is available in Ollama"""
        try:

            models_response = await client.get(f"{self.ollama_url}/api/tags")
            if models_response.status_code == 200:
                models = models_response.json().get("models", [])
                model_names = [model["name"] for model in models]

                if "qwen3:0.6b" not in model_names:

                    logger.info("Pulling qwen3:0.6b model...")
                    pull_response = await client.post(
                        f"{self.ollama_url}/api/pull",
                        json={"name": "qwen3:0.6b"},
                        timeout=300.0,
                    )

                    if pull_response.status_code != 200:
                        logger.warning(
                            "Could not pull qwen3:0.6b model, will attempt to use any available model"
                        )

        except Exception as e:
            logger.warning(f"Could not ensure model availability: {e}")
