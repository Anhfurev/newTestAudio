import os
from ninja import NinjaAPI, Schema
from django.shortcuts import get_object_or_404
from .models import Contract, Product
from dotenv import load_dotenv
from .llm_client import CHAT_MODEL, INTENT_MODEL, client

load_dotenv()
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
Analyze the following User Question and classify its intent into one of two categories: 'DB' or 'PDF'.

RULES FOR CLASSIFICATION:
- Return 'DB' if the question is asking about a specific user's balance, contract number, start/end dates, or a specific insurance product list.
- Return 'PDF' if the question is asking about general information, rules, policies, terms, or instructions.

CRITICAL CONSTRAINT: You must output ONLY the exact word 'DB' or 'PDF'. Do not add punctuation, explanations, or any other words.

User Question: '{question}'
"""
    
    intent_response = client.chat.completions.create(
        model=INTENT_MODEL,
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
You are a smart, polite, and helpful assistant. 
Answer the user's question concisely and clearly based ONLY on the provided Context.

CRITICAL RULE: You MUST write your final response entirely in the Mongolian language (Cyrillic). Do not reply in English.

Context: {context}
User Question: {question}
"""

    answer = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "system", "content": final_prompt}]
    ).choices[0].message.content

    return {
        "intent": intent_response,
        "answer": answer
    }
