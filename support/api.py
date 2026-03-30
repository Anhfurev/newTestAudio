import os
import json
import io
import PyPDF2
from ninja import File, NinjaAPI, Schema, UploadedFile
from openai import OpenAI
from dotenv import load_dotenv
from .models import CustomerBalance, ConversationState, ProductCertificate # Import your model

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
api = NinjaAPI()

class ChatRequest(Schema):
    session_id: str
    message: str


def get_contract_balance(contract_number: str) -> str:
    try:
        balance = CustomerBalance.objects.get(contract_number=contract_number)
        return f"Таны гэрээний үлдэгдэл: {balance.contract_balance}₮"
    except CustomerBalance.DoesNotExist:
        return "Уучлаарай, системд ийм дугаартай гэрээ олдсонгүй."

from .views import search_knowledge_base

@api.post("/chat")
def chat_agent(request, payload: ChatRequest):
    user_input = payload.message.strip()

    # --- 1. Load History ---
    state_obj, _ = ConversationState.objects.get_or_create(session_id=payload.session_id)
    messages = state_obj.history
    if not messages:
        messages = [{"role": "system", "content": "Та бол Mongolian insurance assistant AI 'Mongol AI'."}]

    # --- 2. Classify Intent FIRST ---
    from .ai_architecture import classify_user_intent
    routing_data = classify_user_intent(user_input)
    intent = routing_data.get("intent")
    print(f"DEBUG - Detected Intent: {intent}")

    # --- 3. Execute based on Intent ---
    bot_response_text = ""

    if intent == "check_balance":
        contract_num = routing_data.get("extracted_id")
        if contract_num:
            db_data = get_contract_balance(contract_num)
            bot_response_text = f"Мэдээллийн сангаас шүүсэн хариу: {db_data}"
        else:
            bot_response_text = "Та гэрээний дугаараа оруулна уу."

    elif intent == "check_certificate":
        cert_num = routing_data.get("extracted_id")
        if cert_num:
            bot_response_text = f"Бүтээгдэхүүний эрх шалгаж байна: {cert_num}..."
        else:
            bot_response_text = "Та шалгах бүтээгдэхүүн эсвэл компанийн мэдээллээ оруулна уу."

    elif intent == "rag_search":
        search_query = routing_data.get("optimized_search_query")
        rag_context = search_knowledge_base(search_query)
        final_rag_prompt = f"Контекст:\n{rag_context}\n\nАсуулт: {user_input}"
        temp_messages = messages.copy()
        temp_messages.append({"role": "user", "content": final_rag_prompt})
        ai_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=temp_messages
        )
        bot_response_text = ai_response.choices[0].message.content

    else:
        temp_messages = messages.copy()
        temp_messages.append({"role": "user", "content": user_input})
        ai_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=temp_messages
        )
        bot_response_text = ai_response.choices[0].message.content

    # --- 4. Save History and Return ---
    messages.append({"role": "user", "content": user_input})
    messages.append({"role": "assistant", "content": bot_response_text})
    state_obj.history = messages
    state_obj.save()
    return {"response": bot_response_text}

@api.post("/upload-pdf")
def upload_and_process_pdf(request, file: UploadedFile = File(...)):
    try:
        # 1. Read the PDF directly from the uploaded memory bytes
        pdf_text = ""
        pdf_bytes = file.read()
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pdf_text += text + "\n"

        # 2. Ask OpenAI to extract the data
        prompt = f"""
        You are a data extraction assistant. Read the following Mongolian document and extract the product and company details.
        Return ONLY a JSON object with these exact keys. Use YYYY-MM-DD format for dates. If a field is missing, return null.
        
        Keys: "product_name", "start_date", "end_date", "company_name", "company_register"
        
        Document Text:
        {pdf_text}
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={ "type": "json_object" }
        )

        ai_data = json.loads(response.choices[0].message.content)

        # 3. Save the extracted data to your Database
        new_product = ProductCertificate.objects.create(
            product_name=ai_data.get("product_name", "Тодорхойгүй бүтээгдэхүүн"),
            start_date=ai_data.get("start_date"),
            end_date=ai_data.get("end_date"),
            company_name=ai_data.get("company_name", "Тодорхойгүй компани"),
            company_register=ai_data.get("company_register", "")
        )
        
        # Optional: Save the actual PDF file to the model
        # new_product.source_pdf.save(file.name, file)
        
        return {
            "success": True, 
            "message": f"{new_product.product_name} амжилттай хадгалагдлаа!",
            "extracted_data": ai_data
        }

    except Exception as e:
        return {"success": False, "error": str(e)}