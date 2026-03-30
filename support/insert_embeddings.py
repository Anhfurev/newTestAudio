from langchain_postgres import PGVector
from langchain_ollama import OllamaEmbeddings

# Set up your connection and collection
PGVECTOR_CONNECTION = "postgresql+psycopg://postgres:Moojig0430@localhost:5432/insurance_db"
PGVECTOR_COLLECTION = "pdf_knowledge_base"

embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://127.0.0.1:11434"
)

vector_store = PGVector(
    collection_name=PGVECTOR_COLLECTION,
    connection=PGVECTOR_CONNECTION,
    embeddings=embeddings,
)

# Add your texts
texts = [
    "Таны гэрээний дугаар: 12345",
    "Даатгалын нөхцөл, журам",
    "Жишээ мэдээлэл"
]
vector_store.add_texts(texts)
print("Embeddings inserted!")
