from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# 1. Load PDF
loader = PyPDFLoader("file.pdf")
docs = loader.load()

# 2. Split into chunks
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100
)
chunks = splitter.split_documents(docs)

# 3. Set up embeddings and vector store
embeddings = OllamaEmbeddings(
    model="nomic-embed-text",
    base_url="http://127.0.0.1:11434"
)

vector_store = PGVector(
    connection="postgresql+psycopg://postgres:Moojig0430@localhost:5432/insurance_db",
    collection_name="pdf_knowledge_base",
    embeddings=embeddings,
)

# 4. Add chunks to vector store
vector_store.add_documents(chunks)
