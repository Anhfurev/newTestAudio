import os
from ninja import NinjaAPI, Schema
from django.shortcuts import get_object_or_404
from .models import Contract, Product
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
api = NinjaAPI()

class QuestionSchema(Schema):
    question: str

def get_pdf_answer(question: str):
    # TODO: Integrate with your vector DB or Langchain retriever
    return "PDF доторх мэдээллээс олдсон контекст..."

@api.post("/ask/")
def ask_agent(request, payload: QuestionSchema):
    question = payload.question
    
    # 1. Intent Detection
    intent_prompt = f"""
    Хэрэглэгчийн асуулт: '{question}'
    Хэрэв асуулт үлдэгдэл, гэрээ, эхлэх/дуусах хугацаа, бүтээгдэхүүний тухай байвал 'DB' гэж буцаа.
    Хэрэв ерөнхий мэдээлэл, дүрэм журам, зааврын тухай байвал 'PDF' гэж буцаа.
    Зөвхөн 'DB' эсвэл 'PDF' гэдэг үгийг л буцаана уу.
    """
    
    intent_response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": intent_prompt}],
        temperature=0
    ).choices[0].message.content.strip()

    context = ""

    # 2. Retrieval
    if intent_response == "DB":
        contracts = Contract.objects.all()[:5]
        context = "Өгөгдлийн сангийн мэдээлэл:\n"
        for c in contracts:
            context += f"Бүтээгдэхүүн: {c.product.name}, Үлдэгдэл: {c.balance}, Эхлэх: {c.start_date}, Дуусах: {c.end_date}\n"
    else:
        context = get_pdf_answer(question)

    # 3. Generation
    final_prompt = f"""
    Чи бол Монгол хэлээр хариулдаг ухаалаг туслах. Дараах мэдээлэлд үндэслэн хэрэглэгчийн асуултад товч, тодорхой, эелдэгээр хариул.
    Мэдээлэл (Context): {context}
    Хэрэглэгчийн асуулт: {question}
    """

    answer = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "system", "content": final_prompt}]
    ).choices[0].message.content

    return {
        "intent": intent_response,
        "answer": answer
    }
