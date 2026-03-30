import os
import json
import psycopg2 # Make sure pip install psycopg2-binary is installed
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Connect directly to your PostgreSQL database
conn = psycopg2.connect(
    dbname="insurance_db",
    user="postgres",
    password="Moojig0430", # Your local postgres password
    host="localhost",
    port="5432"
)
cursor = conn.cursor()

def process_json_to_pgvector(json_file_path):
    print(f"Reading {json_file_path}...")
    
    with open(json_file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    if isinstance(data, dict):
        data = [data]

    inserted_count = 0

    for item in data:
        # 1. Create a clean text version for the AI to read
        text_chunk = " ".join([f"{str(k).replace('_', ' ').title()}: {str(v)}." for k, v in item.items()])
        
        if not text_chunk.strip():
            continue

        # 2. Turn the text into a Vector (This is the pgvector part)
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text_chunk
        )
        embedding = response.data[0].embedding

        # 3. Save to DB: The text, the ORIGINAL JSON (metadata), and the Vector
        cursor.execute("""
            INSERT INTO rag_embeddings (text_chunk, metadata, embedding)
            VALUES (%s, %s::jsonb, %s::vector)
        """, (text_chunk, json.dumps(item), embedding))
        
        inserted_count += 1

    # Commit the changes to the database
    conn.commit()
    print(f"Success! {inserted_count} JSON objects turned into pgvectors.")

# Run the function!
if __name__ == "__main__":
    # Replace with the name of the JSON file you are trying to upload
    process_json_to_pgvector("test_policy.json")