import os
import json
from ninja import NinjaAPI, Schema
from openai import OpenAI
from dotenv import load_dotenv
from django.db import connection
from .models import CustomerBalance, ConversationState

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
api = NinjaAPI()

class UserMessage(Schema):
    message: str

def call_ai_intent(user_input):
    prompt = f"""
You are an insurance assistant.

Decide intent ONLY:
- If user asks about contract balance, payment, or personal data → \"query_db\"
- If user question needs additional info (like contract number) → \"ask_question\"
- Otherwise → \"direct_answer\"

Return ONLY JSON:

{{
  \"intent\": \"query_db | ask_question | direct_answer\"
}}

User: {user_input}
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    ).choices[0].message.content
    return json.loads(response)

def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding

def search_rag(query_embedding):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT text_chunk, embedding <-> %s AS score
            FROM rag_embeddings
            ORDER BY score
            LIMIT 3
        """, [query_embedding])
        results = cursor.fetchall()
    # Use strict threshold
    return [r[0] for r in results if r[1] < 0.2]  # tighter threshold

def call_ai_with_context(question, docs):
    context = "\n".join(docs)
    prompt = f"""
Context:
{context}

Question:
{question}

Answer in Mongolian:
"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    ).choices[0].message.content
    return response

def get_contract_balance(contract_number):
    try:
        balance = CustomerBalance.objects.get(contract_number=contract_number)
        return f"Таны үлдэгдэл: {balance.contract_balance}₮"
    except CustomerBalance.DoesNotExist:
        return "Гэрээ олдсонгүй."

def classify_user_intent(user_message: str, chat_history: str = "") -> dict:
    """
    Analyzes the user's message and returns a strictly formatted JSON routing object.
    """
    system_prompt = """
    Та бол Даатгалын AI-ийн 'Intent Classifier' (Зорилго тодорхойлогч) юм.
    Хэрэглэгчийн хүсэлтийг уншаад ЗӨВХӨН доорх JSON бүтцээр хариулна уу.

    Боломжит 'intent' (зорилго) төрлүүд:
    1. "check_balance": Хэрэглэгч гэрээний үлдэгдэл, төлбөр шалгахыг хүссэн үед.
    2. "check_certificate": Бүтээгдэхүүний эрх, хугацаа шалгахыг хүссэн үед.
    3. "rag_search": Даатгалын ерөнхий мэдээлэл, дүрэм, нөхцөл асуусан үед.
    4. "general_chat": Мэндчилгээ, талархал, эсвэл дээрх аль нь ч биш үед.

    JSON Гаралт (Output structure):
    {
        "intent": "check_balance" | "check_certificate" | "rag_search" | "general_chat",
        "extracted_id": "Хэрэв гэрээ эсвэл регистрийн дугаар байвал энд бичнэ, байхгүй бол null",
        "optimized_search_query": "Хэрэв intent нь rag_search байвал, RVector DB-д хайх хамгийн оновчтой түлхүүр үгсийг энд бичнэ. Бусад үед null."
    }
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Message: {user_message}"}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    return json.loads(response.choices[0].message.content)

@api.post("/ai/handle/")
def handle_user_message(request, payload: UserMessage):
    user_input = payload.message
    session_id = request.headers.get("Session-Id") or "default"
    state_obj, _ = ConversationState.objects.get_or_create(session_id=session_id)
    if not hasattr(state_obj, "retry_count"):
        state_obj.retry_count = 0
    if not hasattr(state_obj, "last_intent"):
        state_obj.last_intent = None

    # 1️⃣ STATE
    if getattr(state_obj, "awaiting_contract", False):
        contract_number = user_input.strip()
        data = get_contract_balance(contract_number)
        if data == "Гэрээ олдсонгүй.":
            state_obj.retry_count += 1
            state_obj.save()
            return {"answer": "Ийм гэрээ олдсонгүй. Дахин зөв дугаар оруулна уу"}
        state_obj.awaiting_contract = False
        state_obj.retry_count = 0
        state_obj.save()
        return {"answer": data}

    # 2️⃣ RAG FIRST
    embedding = get_embedding(user_input)
    docs = search_rag(embedding)
    if docs:
        return {"answer": call_ai_with_context(user_input, docs)}

    # 3️⃣ AI INTENT
    ai_result = call_ai_intent(user_input)
    intent = ai_result["intent"]
    if intent in ["ask_question", "query_db"]:
        state_obj.awaiting_contract = True
        state_obj.retry_count = 0
        state_obj.save()
        return {"answer": "Гэрээний дугаараа оруулна уу"}

    # 4️⃣ SAFE FALLBACK
    answer = ai_result.get("answer")
    if not answer:
        return {"answer": "Уучлаарай, би ойлгосонгүй. Та дахин асууна уу."}
    return {"answer": answer}
