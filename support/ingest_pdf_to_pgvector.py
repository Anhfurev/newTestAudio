import os
import psycopg
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
import pdfplumber

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_URL = os.getenv("PGVECTOR_CONNECTION", "postgresql+psycopg://postgres:Moojig0430@localhost:5432/insurance_db")

# PDF and chunking config
CHUNK_SIZE = 400  # tokens/chars
CHUNK_OVERLAP = 50



client = OpenAI(api_key=OPENAI_API_KEY)

def embed_text(text):
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return resp.data[0].embedding

def chunk_text(text):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    return splitter.split_text(text)

def ingest_pdf(pdf_path, source_name):
    with pdfplumber.open(pdf_path) as pdf, psycopg.connect(DB_URL) as conn:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            chunks = chunk_text(text)
            for chunk in chunks:
                embedding = embed_text(chunk)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO rag_embeddings (text_chunk, embedding, source, page)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (chunk, embedding, source_name, page_num)
                    )
        conn.commit()
    print(f"Ingested {pdf_path}")

if __name__ == "__main__":
    # Example usage
    pdf_file = "./your_pdf_file.pdf"  # Change to your PDF path
    ingest_pdf(pdf_file, source_name="your_pdf_file.pdf")
