from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import aiofiles
from typing import List, Optional
import uuid
from datetime import datetime

from services.document_processor import DocumentProcessor
from services.vector_store import VectorStore
from services.rag_service import RAGService

app = FastAPI(title="microRAG", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


os.makedirs("uploads", exist_ok=True)


document_processor = DocumentProcessor()
vector_store = VectorStore()
rag_service = RAGService(vector_store)


class ChatMessage(BaseModel):
    message: str
    collection_id: Optional[str] = None
    debug: Optional[bool] = False


class ChatResponse(BaseModel):
    response: str
    sources: List[str] = []
    debug_info: Optional[dict] = None


class DocumentInfo(BaseModel):
    id: str
    filename: str
    upload_date: datetime
    chunk_count: int


@app.on_event("startup")
async def startup_event():
    await vector_store.initialize()


@app.post("/upload", response_model=dict)
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.endswith((".txt", ".md")):
        raise HTTPException(
            status_code=400, detail="Only .txt and .md files are supported"
        )

    file_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{file_id}{file_extension}"
    file_path = os.path.join("uploads", unique_filename)

    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    try:
        chunks = await document_processor.process_file(file_path, file.filename)
        collection_id = await vector_store.create_collection(file_id)
        await vector_store.add_documents(collection_id, chunks)

        return {
            "id": file_id,
            "filename": file.filename,
            "message": f"Successfully uploaded and processed {file.filename}",
            "chunk_count": len(chunks),
        }
    except Exception as e:

        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
async def chat(chat_message: ChatMessage):
    try:
        response = await rag_service.generate_response(
            chat_message.message, chat_message.collection_id, debug=chat_message.debug
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error generating response: {str(e)}"
        )


@app.get("/documents", response_model=List[DocumentInfo])
async def get_documents():
    try:
        collections = await vector_store.list_collections()
        documents = []

        for collection in collections:

            file_path = None
            for filename in os.listdir("uploads"):
                if filename.startswith(collection["id"]):
                    file_path = os.path.join("uploads", filename)
                    break

            if file_path and os.path.exists(file_path):
                stat = os.stat(file_path)
                original_filename = collection.get("metadata", {}).get(
                    "filename", filename
                )

                documents.append(
                    DocumentInfo(
                        id=collection["id"],
                        filename=original_filename,
                        upload_date=datetime.fromtimestamp(stat.st_ctime),
                        chunk_count=collection.get("vectors_count", 0),
                    )
                )

        return sorted(documents, key=lambda x: x.upload_date, reverse=True)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching documents: {str(e)}"
        )


@app.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    try:

        await vector_store.delete_collection(document_id)

        for filename in os.listdir("uploads"):
            if filename.startswith(document_id):
                file_path = os.path.join("uploads", filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                break

        return {"message": "Document deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error deleting document: {str(e)}"
        )


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
