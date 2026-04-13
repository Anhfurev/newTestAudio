from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
import os
import json
from dotenv import load_dotenv
from .llm_client import CHAT_MODEL, EMBED_MODEL, client

# Моделиудаа импортлох
from .forms import ApartmentLeadForm, ApartmentPublishForm
from .models import ApartmentLead, InsuranceProduct, CustomerBalance, Intent, IntentDetail

# .env файлаас OpenAI түлхүүр унших
load_dotenv()

def chat_page(request):
    """Чат нүүр хуудсыг харуулах"""
    published_apartments = ApartmentLead.objects.filter(
        status=ApartmentLead.Status.PUBLISHED,
    )[:3]
    return render(
        request,
        "chat.html",
        {"published_apartments": published_apartments},
    )


def apartment_page(request):
    apartments = ApartmentLead.objects.filter(status=ApartmentLead.Status.PUBLISHED)
    return render(
        request,
        "apartments.html",
        {
            "form": ApartmentLeadForm(),
            "apartments": apartments,
        },
    )


def submit_apartment_request(request):
    if request.method != "POST":
        return redirect("apartment-page")

    form = ApartmentLeadForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, "Таны байрны хүсэлт бүртгэгдлээ.")
    else:
        messages.error(request, "Бүх шаардлагатай мэдээллээ бөглөнө үү.")

    return redirect("apartment-page")


def agent_login_page(request):
    if request.user.is_authenticated:
        return redirect("agent-dashboard")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        return redirect("agent-dashboard")

    return render(request, "agent_login.html", {"form": form})


@login_required
def agent_dashboard(request):
    pending_leads = ApartmentLead.objects.filter(status=ApartmentLead.Status.PENDING)
    my_listings = ApartmentLead.objects.filter(
        status=ApartmentLead.Status.PUBLISHED,
        assigned_agent=request.user,
    )
    return render(
        request,
        "agent_dashboard.html",
        {
            "pending_leads": pending_leads,
            "my_listings": my_listings,
            "publish_form": ApartmentPublishForm(),
        },
    )


@login_required
@require_POST
def publish_apartment(request, lead_id):
    lead = get_object_or_404(ApartmentLead, pk=lead_id)
    form = ApartmentPublishForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Агентын утасны дугаараа оруулна уу.")
        return redirect("agent-dashboard")

    lead.status = ApartmentLead.Status.PUBLISHED
    lead.assigned_agent = request.user
    lead.agent_name = request.user.get_full_name() or request.user.username
    lead.agent_phone = form.cleaned_data["agent_phone"]
    lead.published_at = timezone.now()
    lead.save(update_fields=[
        "status",
        "assigned_agent",
        "agent_name",
        "agent_phone",
        "published_at",
    ])
    messages.success(request, "Зарыг үндсэн сайт дээр нийтэллээ.")
    return redirect("agent-dashboard")

# --- 1. RAG Хайлтын функц (Vector DB - pgvector) ---
def search_knowledge_base(search_query: str):
    """
    pgvector ашиглан PDF-ээс текст болон эх сурвалжийг хайх.
    """
    try:
        # Хайх үгийг вектор болгох
        embedding_response = client.embeddings.create(
            model=EMBED_MODEL,
            input=search_query
        )
        query_embedding = embedding_response.data[0].embedding

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT text_chunk, metadata, embedding <=> %s::vector AS score
                FROM rag_embeddings
                ORDER BY score ASC
                LIMIT 3
            """, [query_embedding])
            results = cursor.fetchall()
            
        valid_docs = []
        sources = set()

        for text, metadata, score in results:
            if score < 0.85: # 0.85-аас бага зайтай (ойрхон) бол авна
                valid_docs.append(text)
                
                # Metadata-г JSON болгож засах (TypeError-оос сэргийлэх)
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                
                if metadata and isinstance(metadata, dict) and 'source_file' in metadata:
                    sources.add(metadata['source_file'])

        if not valid_docs:
            return None, None
            
        return "\n\n".join(valid_docs), list(sources)
    except Exception as e:
        print(f"RAG Search Error: {e}")
        return None, None

# --- 2. Үндсэн Чат API ---
def chat_api(request):
    if request.method != "POST":
        return JsonResponse({"error": "Зөвхөн POST хүсэлт зөвшөөрөгдөнө"}, status=405)

    try:
        data = json.loads(request.body)
        user_message = data.get("message", "").strip()
        
        # 💡 ШИНЭ: Фронт-эндээс өмнөх чатын түүхийг хүлээж авах (байхгүй бол хоосон list)
        chat_history = data.get("history", [])

        from .ai_architecture import classify_user_intent
        routing_data = classify_user_intent(user_message)

        intent_name = routing_data.get("intent", "general_chat")
        search_query = routing_data.get("optimized_search_query") or user_message
        extracted_id = routing_data.get("extracted_id")

        bot_response_text = ""
        source_info = None

        # =======================================================
        # АЛХАМ 1: СТАТИК ХАРИУЛТ
        # =======================================================
        db_intent = Intent.objects.filter(intent_name__iexact=intent_name).first()
        
        if db_intent:
            detail = db_intent.details.first()
            if detail and detail.answer:
                # 🚨 ЗАСВАР: rag_search-ийг эндээс хасав!
                if intent_name == "greeting":
                    return JsonResponse({"reply": detail.answer, "intent": intent_name})
                else:
                    bot_response_text = detail.answer

        # =======================================================
        # АЛХАМ 2: ЛОГИК ХУВААРИЛАЛТ
        # =======================================================
        if intent_name == "list_products":
            products = InsuranceProduct.objects.filter(is_active=True)
            if not products.exists():
                bot_response_text = "Уучлаарай, одоогоор бүртгэлтэй бүтээгдэхүүн алга байна."
            else:
                lines = [f"{p.icon} **{p.category}:** {p.name}" for p in products]
                bot_response_text = "Манай даатгалын бүтээгдэхүүнүүд:\n" + "\n".join(lines)

        elif intent_name in ["check_balance", "check_certificate"]:
            if not extracted_id or str(extracted_id).lower() in ["null", "none", ""]:
                bot_response_text = "Та гэрээний дугаараа (эсвэл регистрийн дугаараа) хэлнэ үү. Би мэдээллийг тань шалгаад өгье."
            else:
                cert = CustomerBalance.objects.filter(contract_number=extracted_id).first()
                if cert:
                    bot_response_text = (
                        f"✅ Гэрээний мэдээлэл олдлоо:\n"
                        f"💰 Үлдэгдэл: {cert.contract_balance}₮\n"
                        f"🗓 Хугацаа: {cert.coverage_end} хүртэл хүчинтэй."
                    )
                else:
                    bot_response_text = f"Уучлаарай, системд {extracted_id} дугаартай гэрээ олдсонгүй."

        elif intent_name == "rag_search":
            context, sources = search_knowledge_base(search_query)
            
            if context:
                # 💡 ШИНЭ: Илүү хатуу System Prompt болон History ашиглах
                system_prompt = (
    "You are a professional insurance assistant. "
    "Answer the user's question based ONLY on the provided 'Context' information below. "
    "If the answer cannot be found within the Context, DO NOT hallucinate or make up information. "
    "Instead, reply exactly with: 'Энэ талаарх мэдээлэл олдсонгүй'. "
    "You MUST write your final response in the Mongolian language (Cyrillic).\n\n"
    f"Context: {context}"
)
                
                messages = [{"role": "system", "content": system_prompt}]
                messages.extend(chat_history) # Өмнөх яриаг нэмэх
                messages.append({"role": "user", "content": user_message})

                completion = client.chat.completions.create(
                    model=CHAT_MODEL,
                    messages=messages,
                    temperature=0.2 # 💡 Уран сэтгэмжийг багасгах
                )
                bot_response_text = completion.choices[0].message.content
                source_info = sources

        # D. ЕРӨНХИЙ ЧАТ
        if not bot_response_text:
            messages = [{"role": "system", "content": "You are mongolian insurance helper AI."}]
            messages.extend(chat_history)
            messages.append({"role": "user", "content": user_message})

            completion = client.chat.completions.create(
                model=CHAT_MODEL,
                messages=messages
            )
            bot_response_text = completion.choices[0].message.content

        return JsonResponse({
            "reply": bot_response_text,
            "intent": intent_name,
            "sources": source_info
        })

    except Exception as e:
        print(f"CRITICAL ERROR in chat_api: {e}")
        return JsonResponse({"error": "Сервер дээр алдаа гарлаа. Түр хүлээгээд дахин оролдоно уу."}, status=500)