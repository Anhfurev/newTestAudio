import os
import psycopg
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DB_URL = os.getenv("PGVECTOR_CONNECTION", "postgresql://postgres:Moojig0430@localhost:5432/insurance_db")

client = OpenAI(api_key=OPENAI_API_KEY)

def embed_text(text):
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return resp.data[0].embedding

def insert_chunk(text, source="manual", page=1):
    embedding = embed_text(text)
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_embeddings (text_chunk, embedding, source, page)
                VALUES (%s, %s, %s, %s)
                """,
                (text, embedding, source, page)
            )
        conn.commit()
    print(f"Inserted: {text[:40]}...")

if __name__ == "__main__":
    chunks = [
        "Даатгалын гэрээний үлдэгдэл гэдэг нь таны гэрээний даатгалын дансанд байгаа мөнгөн дүн юм.",
        "Нөхөн төлбөр авахын тулд гэрээний дугаараа оруулна уу.",
        "Автомашины даатгал нь осол, хулгай, гал болон бусад эрсдэлээс хамгаална.",
        "Даатгалын хугацаа дуусахад гэрээг сунгах шаардлагатай."
    ]
    for i, chunk in enumerate(chunks, 1):
        insert_chunk(chunk, source="manual", page=i)
