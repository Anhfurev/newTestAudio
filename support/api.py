from concurrent.futures import ThreadPoolExecutor, TimeoutError

def _call_llm(llm, prompt):
    return llm.invoke(prompt)
import signal

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException()
_vector_store = None

def _get_vector_store():
    global _vector_store
    if _vector_store is None:
        embeddings = _get_embeddings()
        _vector_store = PGVector(
            collection_name=PGVECTOR_COLLECTION,
            connection=PGVECTOR_CONNECTION,
            embeddings=embeddings,
        )
    return _vector_store
def _clean_mongolian(text):
    text = text.strip()
    return text
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
    "postgresql+psycopg://postgres:Moojig0430@localhost:5432/insurance_db",
)

PGVECTOR_COLLECTION = os.getenv("PGVECTOR_COLLECTION", "pdf_knowledge_base")


class ChatRequest(Schema):
    session_id: str
    message: str


def _ollama_llm():
    if OllamaLLM is None:
        raise RuntimeError("Ollama not installed")

    return OllamaLLM(
        model=OLLAMA_MODEL,
        base_url="http://127.0.0.1:11434",
        temperature=0.3,
        top_p=0.9,
        repeat_penalty=1.1,
    )


def _get_embeddings():
    if OllamaEmbeddings is None:
        return None

    return OllamaEmbeddings(
        model=EMBED_MODEL,
        base_url="http://127.0.0.1:11434"
    )


def _extract_contract_number(message: str) -> str:
    digits = re.findall(r"\d+", message)
    return digits[0] if digits else message.strip()


@api.post("/chat")
def chat_agent(request, payload: ChatRequest):
    user_msg = payload.message.strip()
    user_msg_lower = user_msg.lower()

    state, _ = ConversationState.objects.get_or_create(
        session_id=payload.session_id
    )

    # =========================
    # 1️⃣ Contract flow
    # =========================
    if state.awaiting_contract:
        contract_number = _extract_contract_number(user_msg)

        try:
            balance = CustomerBalance.objects.get(
                contract_number=contract_number
            )

            reply = f"Таны дансны үлдэгдэл: ${balance.contract_balance}"

        except CustomerBalance.DoesNotExist:
            reply = "Ийм гэрээ олдсонгүй. Дахин шалгана уу."

        state.awaiting_contract = False
        state.save(update_fields=["awaiting_contract"])

        return {"response": reply}

    # =========================
    # 2️⃣ Greeting
    # =========================
    if any(word in user_msg_lower for word in ["сайн уу", "сайн байна уу", "юу байна"]):
        state.awaiting_contract = True
        state.save(update_fields=["awaiting_contract"])

        return {"response": "Сайн байна уу! Гэрээний дугаараа бичнэ үү."}

    # =========================
    # 3️⃣ Intent DB
    # =========================
    intent = CustomerIntent.objects.filter(
        intent__icontains=user_msg_lower
    ).first()

    if intent:
        if "balance" in intent.intent.lower():
            state.awaiting_contract = True
            state.save(update_fields=["awaiting_contract"])

            return {
                "response": f"{intent.answer}\n\nГэрээний дугаараа бичнэ үү."
            }

        return {"response": intent.answer}

    # =========================
    # 4️⃣ RAG (PGVector)
    # =========================
    if PGVector and ("?" in user_msg or any(word in user_msg_lower for word in ["юу", "яаж", "хэзээ"])) and len(user_msg) > 5:
        try:
            vector_store = _get_vector_store()
            docs = vector_store.similarity_search(user_msg, k=3)

            if docs:
                context = "\n\n".join([
                    f"- {d.page_content.strip()[:300]}" for d in docs
                ])

                prompt = f"""<|im_start|>system\nYou are a professional assistant fluent in Mongolian. Always respond naturally and correctly in Mongolian. Avoid awkward translation style.\n<|im_end|>\n\n<|im_start|>user\nДараах мэдээллийг ашиглан зөвхөн Монгол хэл дээр хариулна уу. Хэрэв мэдээлэл байхгүй бол 'Мэдэхгүй байна' гэж хэлнэ. Use the context ONLY if relevant. Do not copy blindly.\n\n{context}\n\nАсуулт: {user_msg}\n<|im_end|>\n\n<|im_start|>assistant\n"""

                llm = _ollama_llm()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_call_llm, llm, prompt)
                    try:
                        answer = future.result(timeout=20)
                    except TimeoutError:
                        return {"response": "AI удаан байна. Дахин оролдоно уу."}
                answer = _clean_mongolian(answer)

                return {"response": answer}

        except Exception as e:
            print("RAG ERROR:", str(e))

    # =========================
    # 5️⃣ AI fallback
    # =========================
    try:
        llm = _ollama_llm()
        prompt = f"""<|im_start|>system\nYou are a professional Mongolian language assistant.\nAlways respond in natural, fluent Mongolian.\n<|im_end|>\n\n<|im_start|>user\n{user_msg}\n<|im_end|>\n\n<|im_start|>assistant\n"""
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call_llm, llm, prompt)
            try:
                answer = future.result(timeout=20)
            except TimeoutError:
                return {"response": "AI удаан байна. Дахин оролдоно уу."}
        answer = _clean_mongolian(answer)

        return {"response": answer}

    except Exception as e:
        print("OLLAMA ERROR:", str(e))
        return {"response": "AI ажиллахгүй байна. Console-г шалгана уу."}