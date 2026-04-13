import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# ==========================================
# 1. DJANGO ТОХИРГОО (Скриптийг гаднаас ажиллуулах үед)
# ==========================================
import django
# АНХААР: 'your_project_name' гэдгийг өөрийнхөө Django төслийн жинхэнэ нэрээр солиорой! 
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agentapp.settings') 
django.setup()

from django.db import connection

# ==========================================
# 2. OPENAI ТОХИРГОО
# ==========================================
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

KNOWLEDGE_BASE_DIR = "knowledge_base"
all_data = []

# ==========================================
# 3. ХАВТАСНААС БҮХ JSON ФАЙЛЫГ УНШИХ
# ==========================================
print("🔍 Knowledge base хавтсыг уншиж байна...")
for filename in os.listdir(KNOWLEDGE_BASE_DIR):
    if filename.endswith(".json"):
        filepath = os.path.join(KNOWLEDGE_BASE_DIR, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                file_data = json.load(f)
                all_data.extend(file_data)
                print(f"✅ Уншсан: {len(file_data)} дүрэм -> {filename} файлаас")
        except json.JSONDecodeError:
            print(f"⚠️ Анхаар: '{filename}' файл хоосон эсвэл формат алдаатай байна.")

print(f"\n🚀 Нийт бааз руу оруулахад бэлэн болсон дүрэм: {len(all_data)}\n")

# ==========================================
# 4. ШИНЭ JSON БҮТЦЭЭР МЕТАДАТА-ТАЙ ХАДГАЛАХ
# ==========================================
with connection.cursor() as cursor:
    # (Сонголттой) Хуучин өгөгдлөө цэвэрлэхийг хүсвэл доорх мөрийг идэвхжүүлж болно:
    # cursor.execute("DELETE FROM rag_embeddings")
    cursor.execute("TRUNCATE TABLE rag_embeddings;") 
    print("🧹 Хуучин өгөгдлийг цэвэрлэлээ...")

    for item in all_data:
        # 🚨 ХАМГААЛАЛТ: Шинэ формат мөн эсэхийг шалгах
        if "training_data" not in item:
            print(f"⚠️ Алгаслаа: '{item.get('category', 'Unknown')}' хуучин форматтай байна.")
            continue

        # 1. Хайлт хийхэд зориулсан текст бэлтгэх (Embedding-д зориулав)
        primary = item["training_data"]["primary_question"]
        alternatives = ", ".join(item["training_data"]["alternative_questions"])
        search_text = f"Intent: {item['intent_name']}. Questions: {primary}, {alternatives}"
        
        # 2. AI-д уншуулах үндсэн хариулт (Text Chunk)
        answer = item["knowledge_base"]["static_answer"]
        final_chunk = f"Category: {item['intent_name']}. Response: {answer}"

        # 3. БҮТЭН JSON-ийг Metadata болгож бэлтгэх (JSONB-д зориулсан string)
        metadata_json = json.dumps(item)

        # 4. OpenAI-аар Embedding (Вектөр тоо) үүсгэх
        print(f"🧠 Embedding үүсгэж байна: {item['intent_id']}...")
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=search_text
        )
        embedding = response.data[0].embedding

        # 5. PostgreSQL руу бүх 3 утгыг (Chunk, Embedding, Metadata) хадгалах
        cursor.execute("""
            INSERT INTO rag_embeddings (text_chunk, embedding, metadata)
            VALUES (%s, %s::vector, %s::jsonb)
        """, [final_chunk, embedding, metadata_json])
        
        print(f"✅ Бааз руу амжилттай орлоо: {item['intent_id']}")

print("\n🎉 БАЯР ХҮРГЭЕ! Бүх өгөгдөл Метадата-тайгаа амжилттай орлоо.")