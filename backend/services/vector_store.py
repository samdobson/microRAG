import os
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self):
        self.client = None
        self.embedding_model = None
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def initialize(self):
        """Initialize the vector store connection and embedding model"""
        qdrant_host = os.getenv("QDRANT_HOST", "localhost")
        qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))

        self.client = QdrantClient(host=qdrant_host, port=qdrant_port)

        loop = asyncio.get_event_loop()
        self.embedding_model = await loop.run_in_executor(
            self.executor, lambda: SentenceTransformer("all-MiniLM-L6-v2")
        )

    async def create_collection(self, collection_name: str) -> str:
        """Create a new collection for document vectors"""
        try:

            collections = self.client.get_collections().collections
            if any(col.name == collection_name for col in collections):
                return collection_name

            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=384, distance=models.Distance.COSINE
                ),
            )
            return collection_name
        except Exception as e:
            logger.error(f"Error creating collection {collection_name}: {e}")
            raise

    async def add_documents(
        self, collection_name: str, documents: List[Dict[str, Any]]
    ):
        """Add documents to the vector store"""
        try:
            points = []
            texts = [doc["content"] for doc in documents]

            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                self.executor, self.embedding_model.encode, texts
            )

            for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
                points.append(
                    models.PointStruct(
                        id=i,
                        vector=embedding.tolist(),
                        payload={
                            "content": doc["content"],
                            "metadata": doc.get("metadata", {}),
                        },
                    )
                )

            self.client.upsert(collection_name=collection_name, points=points)

        except Exception as e:
            logger.error(f"Error adding documents to {collection_name}: {e}")
            raise

    async def search(
        self, collection_name: str, query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        try:

            loop = asyncio.get_event_loop()
            query_embedding = await loop.run_in_executor(
                self.executor, self.embedding_model.encode, [query]
            )

            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding[0].tolist(),
                limit=limit,
                with_payload=True,
            )

            results = []
            for hit in search_result:
                results.append(
                    {
                        "content": hit.payload["content"],
                        "metadata": hit.payload.get("metadata", {}),
                        "score": hit.score,
                    }
                )

            return results
        except Exception as e:
            logger.error(f"Error searching in {collection_name}: {e}")
            raise

    async def list_collections(self) -> List[Dict[str, Any]]:
        """List all collections"""
        try:
            collections = self.client.get_collections().collections
            result = []

            for col in collections:
                info = self.client.get_collection(col.name)
                result.append(
                    {
                        "id": col.name,
                        "name": col.name,
                        "vectors_count": info.points_count if info else 0,
                    }
                )

            return result
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            raise

    async def delete_collection(self, collection_name: str):
        """Delete a collection"""
        try:
            self.client.delete_collection(collection_name)
        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}")
            raise
