from django.shortcuts import render


def chat_page(request):
    return render(request, "chat.html")


# --- RAG Search Function ---
from django.db import connection
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

from django.db import connection

def search_knowledge_base(search_query: str) -> str:
    # 1. Get the embedding
    embedding_response = client.embeddings.create(
        model="text-embedding-3-small",
        input=search_query
    )
    query_embedding = embedding_response.data[0].embedding

    # 2. Search pgvector using Cosine Distance (<=>)
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT text_chunk, embedding <=> %s::vector AS score
            FROM rag_embeddings
            ORDER BY score ASC
            LIMIT 3
        """, [query_embedding])
        results = cursor.fetchall()
        
    # --- DEBUG: Print the actual math scores to your terminal! ---
    print("--- PGVECTOR SCORES ---")
    for r in results:
        print(f"Score: {r[1]:.4f} | Text: {r[0]}")
    print("-----------------------")
        
    # 3. Loosen the threshold
    # With Cosine Distance, 0.0 is a perfect match, and 1.0 is completely unrelated.
    # 0.5 is a very safe middle ground to start with.
    docs = [r[0] for r in results if r[1] < 0.9]
    
    if not docs:
        return "No relevant information found in the insurance documents."
        
    return "\n\n".join(docs)