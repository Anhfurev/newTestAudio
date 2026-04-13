import os
import json
from dotenv import load_dotenv
from django.db import connection
from .llm_client import EMBED_MODEL, INTENT_MODEL, client

# Өөрийн support апп-ын моделийг импортлох
from support.models import Intent

load_dotenv()

# --- 1. RAG & DATABASE SEARCH (pgvector) ---
def get_embedding(text):
    response = client.embeddings.create(
        model=EMBED_MODEL,
        input=text
    )
    return response.data[0].embedding

def search_rag(query_text):
    """
    PDF-ээс текст хайх (pgvector)
    """
    try:
        query_embedding = get_embedding(query_text)
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT text_chunk, embedding <=> %s::vector AS score
                FROM rag_embeddings
                ORDER BY score
                LIMIT 3
            """, [query_embedding])
            results = cursor.fetchall()
        # 0.85-аас бага (ойрхон) байгааг нь авна
        return [r[0] for r in results if r[1] < 0.85]
    except Exception as e:
        print(f"RAG Search Error: {e}")
        return []

# --- 2. INTENT CLASSIFIER (Сайжруулсан) ---
def classify_user_intent(user_message: str, chat_history: str = "") -> dict:
    system_prompt = """
    Та бол Даатгалын AI-ийн 'Intent Classifier' юм. 
    ЗӨВХӨН доорх JSON бүтцээр хариулна уу.

    --- ИНТЕНТ ТӨРЛҮҮД ---
    1. "greeting": 'Сайн уу', 'Мэндээ', 'Hi' гэх мэт мэндчилгээнд. (МАШ ЧУХАЛ: Үүнийг 'rag_search' гэж ангилж БОЛОХГҮЙ!)
    2. "check_balance": Гэрээний үлдэгдэл, төлбөр шалгах хүсэлт.
    3. "list_products": Даатгалын жагсаалт харах хүсэлт.
    4. "rag_search": Даатгалын нарийн дүрэм, заавар, PDF-ээс хайх мэдээлэл.
    5. "general_chat": Бусад.

    --- ID ОЛБОРЛОХ ---
    Хэрэв мессеж ЗӨВХӨН ТОO (жишээ нь: '12345') байвал intent: 'check_balance', extracted_id: '12345' гэж авна.

    JSON Гаралт:
    {
        "intent": "нэр",
        "extracted_id": "ID эсвэл null",
        "optimized_search_query": "Хайх үг"
    }
    """
    
    response = client.chat.completions.create(
        model=INTENT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Message: {user_message}"}
        ],
        temperature=0.0 
    )

    try:
        routing_data = json.loads(response.choices[0].message.content)
        return routing_data
    except:
        return {"intent": "general_chat", "extracted_id": None, "optimized_search_query": user_message}

# --- 3. DATABASE ANSWER RETRIEVAL (Senior-ийн хүссэн функц) ---
def get_answer_from_db(intent_name: str):
    """
    AI-ийн таньсан Intent-ээр баазаас (PostgreSQL) хариулт шүүх
    """
    try:
        # Том жижиг үсэг хамаарахгүйгээр хайна
        intent_obj = Intent.objects.filter(intent_name__iexact=intent_name).first()
        
        if intent_obj:
            # Related name 'details' ашиглан IntentDetail-ээс хариулт авах
            detail = intent_obj.details.first() 
            if detail:
                return detail.answer
        return None
    except Exception as e:
        print(f"DB Retrieval Error: {e}")
        return None