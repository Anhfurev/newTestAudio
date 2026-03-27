import os
import sys

from langchain_community.document_loaders import PDFPlumberLoader
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter


PGVECTOR_CONNECTION = os.getenv(
    "PGVECTOR_CONNECTION",
    "postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
)
PGVECTOR_COLLECTION = os.getenv("PGVECTOR_COLLECTION", "pdf_knowledge_base")
EMBED_MODEL = "nomic-embed-text"


def ingest_document(file_path: str) -> None:
    loader = PDFPlumberLoader(file_path)
    docs = loader.load()

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = splitter.split_documents(docs)

    embeddings = OllamaEmbeddings(model=EMBED_MODEL)

    PGVector.from_documents(
        documents=splits,
        embedding=embeddings,
        connection=PGVECTOR_CONNECTION,
        collection_name=PGVECTOR_COLLECTION,
    )
    print("PDF successfully ingested into Postgres/pgvector.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python ingest_pdf.py /path/to/file.pdf")
        raise SystemExit(1)
    ingest_document(sys.argv[1])
