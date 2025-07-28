import os
from typing import List, Dict, Any
import aiofiles
import markdown
import re
from dataclasses import dataclass


@dataclass
class DocumentChunk:
    content: str
    metadata: Dict[str, Any]


class DocumentProcessor:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def process_file(
        self, file_path: str, original_filename: str
    ) -> List[Dict[str, Any]]:
        """Process a file and return chunks"""
        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension == ".md":
            return await self._process_markdown(file_path, original_filename)
        elif file_extension == ".txt":
            return await self._process_text(file_path, original_filename)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

    async def _process_text(
        self, file_path: str, original_filename: str
    ) -> List[Dict[str, Any]]:
        """Process a plain text file"""
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()

        chunks = self._create_chunks(content)

        return [
            {
                "content": chunk.content,
                "metadata": {
                    "filename": original_filename,
                    "file_type": "text",
                    "chunk_index": i,
                    **chunk.metadata,
                },
            }
            for i, chunk in enumerate(chunks)
        ]

    async def _process_markdown(
        self, file_path: str, original_filename: str
    ) -> List[Dict[str, Any]]:
        """Process a markdown file"""
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            content = await f.read()

        md = markdown.Markdown()
        html = md.convert(content)
        plain_text = self._html_to_text(html)

        headers = self._extract_headers(content)

        chunks = self._create_chunks(plain_text)

        return [
            {
                "content": chunk.content,
                "metadata": {
                    "filename": original_filename,
                    "file_type": "markdown",
                    "chunk_index": i,
                    "headers": self._get_relevant_headers(chunk.content, headers),
                    **chunk.metadata,
                },
            }
            for i, chunk in enumerate(chunks)
        ]

    def _create_chunks(self, text: str) -> List[DocumentChunk]:
        """Split text into overlapping chunks"""

        sentences = re.split(r"(?<=[.!?])\s+", text)

        chunks = []
        current_chunk = ""
        current_sentences = []

        for sentence in sentences:

            test_chunk = current_chunk + " " + sentence if current_chunk else sentence

            if len(test_chunk) <= self.chunk_size:
                current_chunk = test_chunk
                current_sentences.append(sentence)
            else:

                if current_chunk:
                    chunks.append(
                        DocumentChunk(
                            content=current_chunk.strip(),
                            metadata={"sentence_count": len(current_sentences)},
                        )
                    )

                if self.chunk_overlap > 0 and current_sentences:

                    overlap_sentences = (
                        current_sentences[-2:]
                        if len(current_sentences) > 1
                        else current_sentences
                    )
                    current_chunk = " ".join(overlap_sentences) + " " + sentence
                    current_sentences = overlap_sentences + [sentence]
                else:
                    current_chunk = sentence
                    current_sentences = [sentence]

        if current_chunk:
            chunks.append(
                DocumentChunk(
                    content=current_chunk.strip(),
                    metadata={"sentence_count": len(current_sentences)},
                )
            )

        return chunks

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text"""

        clean = re.compile("<.*?>")
        text = re.sub(clean, "", html)

        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _extract_headers(self, markdown_content: str) -> List[Dict[str, str]]:
        """Extract headers from markdown content"""
        headers = []
        lines = markdown_content.split("\n")

        for line_num, line in enumerate(lines):
            if line.strip().startswith("#"):

                level = 0
                for char in line:
                    if char == "#":
                        level += 1
                    else:
                        break

                header_text = line.strip("#").strip()
                headers.append(
                    {"level": level, "text": header_text, "line_number": line_num}
                )

        return headers

    def _get_relevant_headers(
        self, chunk_content: str, headers: List[Dict[str, str]]
    ) -> List[str]:
        """Find headers that might be relevant to this chunk"""
        relevant_headers = []

        for header in headers:

            if header["text"].lower() in chunk_content.lower():
                relevant_headers.append(f"H{header['level']}: {header['text']}")

        return relevant_headers
