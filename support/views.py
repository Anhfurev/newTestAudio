from django.shortcuts import render


def chat_page(request):
    return render(request, "chat.html")


# --- RAG Search Function ---
from django.db import connection
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def search_knowledge_base(search_query: str) -> str:
    """Searches the PDF embeddings in PostgreSQL for general insurance knowledge."""
    # 1. Get the embedding for the AI's search query
    embedding_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=search_query
    )
    query_embedding = embedding_response.data[0].embedding

    # 2. Search pgvector
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT text_chunk, embedding <-> %s::vector AS score
            FROM rag_embeddings
            ORDER BY score
            LIMIT 3
        """, [query_embedding])
        results = cursor.fetchall()
    # Filter by a strict threshold and join the text
    docs = [r[0] for r in results if r[1] < 1.0]  # Adjust threshold as needed
    if not docs:
        return "No relevant information found in the insurance documents."
    return "\n\n".join(docs)


