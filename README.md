# Local AI Agent (Django + Ollama + pgvector)

This project implements your workflow:

- Intent lookup from `CustomerIntent`
- Ask for contract number and resolve balance from `CustomerBalance`
- RAG fallback over PDF chunks stored in Postgres pgvector

## 1) Create virtual environment and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2) Ensure Ollama models are present

```bash
ollama run qwen2.5:7b
ollama pull nomic-embed-text
```

## 3) Run Postgres with pgvector (Docker example)

```bash
docker run --name pgvector-local \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=postgres \
  -p 5432:5432 \
  -d pgvector/pgvector:pg16
```

Enable extension:

```bash
docker exec -it pgvector-local psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## 4) Set environment variables

```bash
export POSTGRES_DB=postgres
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432

export OLLAMA_TEXT_MODEL=qwen
export OLLAMA_EMBED_MODEL=nomic-embed-text
export PGVECTOR_CONNECTION="postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
export PGVECTOR_COLLECTION="pdf_knowledge_base"
```

## 5) Migrate and run server

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open:

- Chat UI: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Admin: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

## 6) Seed data

Use admin to create:

- `CustomerIntent` rows (intent + answer)
- `CustomerBalance` rows (contract number + contract balance)

## 7) Ingest your PDF into pgvector

```bash
python ingest_pdf.py "/absolute/path/to/your_qa.pdf"
```

## Notes

- If intent lookup misses, the API falls back to RAG.
- `session_id` from frontend local storage is used to track `awaiting_contract`.
- Main endpoint: `POST /api/chat` with body:

```json
{
  "session_id": "abc123",
  "message": "What is my renewal policy?"
}
```
# newTestAudio
