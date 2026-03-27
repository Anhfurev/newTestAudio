import os
import re

from ninja import NinjaAPI, Schema

from .models import ConversationState, CustomerBalance, CustomerIntent

try:
    from langchain_ollama import OllamaEmbeddings, OllamaLLM
    from langchain_postgres import PGVector
except Exception:
    OllamaEmbeddings = None
    OllamaLLM = None
    PGVector = None

api = NinjaAPI()

OLLAMA_MODEL = os.getenv("OLLAMA_TEXT_MODEL", "qwen2.5:7b")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
PGVECTOR_CONNECTION = os.getenv(
    "PGVECTOR_CONNECTION",
    "postgresql+psycopg://postgres:postgres@localhost:5432/postgres",
)
PGVECTOR_COLLECTION = os.getenv("PGVECTOR_COLLECTION", "pdf_knowledge_base")


class ChatRequest(Schema):
    session_id: str
    message: str


def _ollama_llm():
    if OllamaLLM is None:
        raise RuntimeError("LangChain/Ollama dependencies are missing.")
    return OllamaLLM(model=OLLAMA_MODEL)


def _extract_contract_number(message: str) -> str:
    digits = re.findall(r"\d+", message)
    if not digits:
        return message.strip()
    return digits[0]


@api.post("/chat")
def chat_agent(request, payload: ChatRequest):
    user_msg = payload.message.strip()
    user_msg_lower = user_msg.lower()
    state, _ = ConversationState.objects.get_or_create(session_id=payload.session_id)

    # 1️⃣ If waiting for contract number
    if state.awaiting_contract:
        contract_number = _extract_contract_number(user_msg)
        try:
            balance_record = CustomerBalance.objects.get(contract_number=contract_number)
            reply = f"Таны дансны үлдэгдэл бол ${balance_record.contract_balance}."
        except CustomerBalance.DoesNotExist:
            reply = "Би энэ гэрээний дугаартай дансны үлдэгдлийг олж чадаагүй. Дахин шалгаж үзнэ үү."
        state.awaiting_contract = False
        state.save(update_fields=["awaiting_contract"])
        return {"response": reply}

    # 2️⃣ Greetings
    if any(word in user_msg_lower for word in ["сайн уу", "сайн байна уу"]):
        state.awaiting_contract = True
        state.save(update_fields=["awaiting_contract"])
        return {"response": "Сайн байна уу! Гэрээний дугаараа хэлээрэй?"}

    # 3️⃣ Check CustomerIntent table
    intent_record = CustomerIntent.objects.filter(intent__icontains=user_msg).first()
    if intent_record:
        state.awaiting_contract = True
        state.save(update_fields=["awaiting_contract"])
        return {"response": f"{intent_record.answer}\n\nТа гэрээний дугаараа хэлээрэй?"}

    # 4️⃣ RAG via PGVector
    if OllamaEmbeddings and PGVector:
        try:
            embeddings = OllamaEmbeddings(model=EMBED_MODEL)
            vector_store = PGVector(
                collection_name=PGVECTOR_COLLECTION,
                connection=PGVECTOR_CONNECTION,
                embeddings=embeddings,
            )
            docs = vector_store.similarity_search(user_msg, k=2)
            if docs:
                context = "\n".join(d.page_content for d in docs)
                rag_prompt = (
                    "Энэ контекстийг ашиглан асуултад хариулна уу. "
                    "Хэрэв хариулт контекстэд байхгүй бол 'Мэдэхгүй байна' гэж хариулна уу.\n\n"
                    f"Context:\n{context}\n\nQuestion: {user_msg}"
                )
                llm = _ollama_llm()
                rag_answer = llm.invoke(rag_prompt)
                return {"response": rag_answer}
        except Exception:
            return {"response": "PGVector эсвэл Ollama дээр асуудал гарлаа. Дараа дахин оролдоно уу."}

    # 5️⃣ Fallback
    try:
        llm = _ollama_llm()
        free_answer = llm.invoke(user_msg)
        return {"response": free_answer}
    except Exception:
        return {"response": "AI-д хариулах боломжгүй байна. Дараа дахин оролдоно уу."}