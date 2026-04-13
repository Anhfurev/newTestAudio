import os
import json
import io
import asyncio
import pdfplumber
import edge_tts
from django.db.models import Q
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from ninja import File, NinjaAPI, Schema, UploadedFile
from dotenv import load_dotenv
# Import own models and functions
from .models import CustomerBalance, ConversationState, InsuranceProduct, Intent, IntentDetail
from .views import search_knowledge_base
from .ai_architecture import classify_user_intent
from .llm_client import CHAT_MODEL, client

# Configuration
load_dotenv()
api = NinjaAPI()

# Request schema
class ChatRequest(Schema):
    session_id: str
    message: str

class TTSRequest(Schema):
    text: str

# ==========================================
# 1. HELPER FUNCTIONS & FAST PATH
# ==========================================
# Direct keyword mapping without calling AI (Cache/Speed Optimization)
QUICK_MAP = {
    "сайн уу": "greeting",
    "сайн байна уу": "greeting",
    "мэнд": "greeting",
    "жагсаалт": "list_products",
    "бүтээгдэхүүн": "list_products",
    "төрөл": "list_products",
    "даатгалууд": "list_products",
    "үлдэгдэл": "check_balance",
}


def extract_contract_id(text: str):
    digits = "".join(filter(str.isdigit, text))
    return digits or None


async def _edge_tts_bytes(text: str, voice: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice, rate="+0%")
    audio_chunks = []
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            audio_chunks.append(chunk.get("data", b""))
    return b"".join(audio_chunks)


def _edge_tts_stream_chunks(text: str, voice: str):
    """Yield Edge TTS audio chunks progressively for HTTP streaming."""
    async def producer(queue: asyncio.Queue):
        communicate = edge_tts.Communicate(text, voice, rate="+0%")
        try:
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio":
                    data = chunk.get("data", b"")
                    if data:
                        await queue.put(data)
        finally:
            await queue.put(None)

    loop = asyncio.new_event_loop()
    queue: asyncio.Queue = asyncio.Queue()
    task = None

    try:
        asyncio.set_event_loop(loop)
        task = loop.create_task(producer(queue))
        while True:
            item = loop.run_until_complete(queue.get())
            if item is None:
                break

            yield item
    finally:
        if task and not task.done():
            task.cancel()
            try:
                loop.run_until_complete(task)
            except Exception:
                pass
        loop.close()
        asyncio.set_event_loop(None)


def _edge_tts(text: str) -> tuple[bytes, str]:
    """Convert text to speech using Microsoft Edge TTS."""
    voice = "mn-MN-BataaNeural"
    try:
        audio = asyncio.run(_edge_tts_bytes(text, voice))
        if not audio:
            print(f"[TTS][ERROR] Edge TTS returned empty audio | voice={voice}")
            return b"", ""

        print(f"[TTS] Edge audio received | bytes={len(audio)} | voice={voice}")
        return audio, "audio/mpeg"
    except RuntimeError:
        # Fallback for environments where an event loop is already active.
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            audio = loop.run_until_complete(_edge_tts_bytes(text, voice))
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        if not audio:
            print(f"[TTS][ERROR] Edge TTS returned empty audio (fallback loop) | voice={voice}")
            return b"", ""

        print(f"[TTS] Edge audio received (fallback loop) | bytes={len(audio)} | voice={voice}")
        return audio, "audio/mpeg"
    except Exception as e:
        print(f"[TTS][ERROR] Edge request exception: {e}")
        return b"", ""


def text_to_speech(text: str) -> tuple[bytes, str]:
    """Convert text to speech using Edge TTS only."""
    return _edge_tts(text)


def get_contract_info(contract_number: str) -> str:
    """Helper function to retrieve contract information"""
    try:
        balance = CustomerBalance.objects.get(contract_number=contract_number)
        return (f"📝 Гэрээний дугаар: {contract_number}\n"
                f"💰 Үлдэгдэл: {balance.contract_balance:,.2f}₮\n"
                f"🗓 Хамрах хугацаа: {balance.coverage_start} - {balance.coverage_end}")
    except CustomerBalance.DoesNotExist:
        return f"Уучлаарай, {contract_number} дугаартай гэрээ системд олдсонгүй."


def route_user_input(user_input: str):
    """Unified routing for both typed and speech-transcribed text."""
    user_input_lower = user_input.lower()
    intent_name = None
    db_response = None
    db_source = None
    extracted_id = extract_contract_id(user_input)

    match = IntentDetail.objects.filter(
        Q(alternative_intent__icontains=user_input_lower)
    ).select_related('intent').first()

    if match:
        db_response, db_source = match.answer, match.source_pdf
        intent_name = match.intent.intent_name
        print(f"[CHAT-ROUTE] DB intent_detail hit -> intent={intent_name} source={db_source}")

    if not intent_name:
        intent_name = next((v for k, v in QUICK_MAP.items() if k in user_input_lower), None)
        if intent_name:
            print(f"[CHAT-ROUTE] QUICK_MAP -> intent={intent_name} extracted_id={extracted_id}")

    if not intent_name and not db_response:
        routing_data = classify_user_intent(user_input)
        intent_name = routing_data.get("intent", "general_chat")
        extracted_id = routing_data.get("extracted_id") or extracted_id
        print(f"[CHAT-ROUTE] CLASSIFIER -> intent={intent_name} extracted_id={extracted_id}")

        db_intent = Intent.objects.filter(intent_name__iexact=intent_name).first()
        if db_intent:
            detail = db_intent.details.first()
            if detail and detail.answer:
                db_response, db_source = detail.answer, detail.source_pdf
                print(f"[CHAT-ROUTE] DB intent fallback hit -> intent={intent_name} source={db_source}")

    return intent_name, db_response, db_source, extracted_id


# ==========================================
# 2. MAIN CHAT (STREAMING ENDPOINT)
# ==========================================

@api.post("/chat-stream")
def chat_agent_stream(request, payload: ChatRequest):
    user_input = payload.message.strip()
    session_id = payload.session_id
    print(f"[CHAT] session={session_id} input={user_input}")

    # 1. Load session and conversation history
    state_obj, _ = ConversationState.objects.get_or_create(session_id=session_id)
    history = state_obj.history or []

    intent_name, db_response, db_source, extracted_id = route_user_input(user_input)

    # Pre-built filler MP3 URLs — 0 ms latency (no edge-tts call needed)
    import random
    # Each value is a list of /static/audio/*.mp3 paths; one is chosen randomly.
    FILLER_URLS = {
        "check_balance": [
            "/static/audio/filler_balance_0.mp3",
            "/static/audio/filler_balance_1.mp3",
            "/static/audio/filler_balance_2.mp3",
        ],
        "check_certificate": [
            "/static/audio/filler_cert_0.mp3",
            "/static/audio/filler_cert_1.mp3",
        ],
        "rag_search": [
            "/static/audio/filler_rag_0.mp3",
            "/static/audio/filler_rag_1.mp3",
            "/static/audio/filler_rag_2.mp3",
        ],
        "general_chat": [
            "/static/audio/filler_chat_0.mp3",
            "/static/audio/filler_chat_1.mp3",
        ],
    }

    # 4. STREAM GENERATOR
    def event_stream():
        final_reply = ""
        is_verified = False
        source = None

        # --- A. Greeting short-circuit (no GPT call) ---
        if intent_name == "greeting":
            final_reply = "Сайн байна уу! 'Монгол Даатгал'-ын туслах байна. Танд юугаар туслах вэ?"
            is_verified = True
            print("[CHAT-HANDLER] greeting short-circuit")
            yield f"data: {json.dumps({'reply': final_reply, 'is_verified': True})}\n\n"

        # --- B. Found in DB (static answer) ---
        elif db_response:
            final_reply = db_response
            source = db_source
            is_verified = True
            print(f"[CHAT-HANDLER] static_db_response intent={intent_name}")
            yield f"data: {json.dumps({'reply': final_reply, 'source': source, 'is_verified': True})}\n\n"

        # --- C. List products (dynamic DB) ---
        elif intent_name == "list_products":
            print("[CHAT-HANDLER] list_products")
            prods = InsuranceProduct.objects.filter(is_active=True)
            if prods.exists():
                lines = [f"🔹 {p.name} ({p.category})" for p in prods]
                final_reply = "Our insurance products:\n" + "\n".join(lines)
            else:
                final_reply = "No active products are available at the moment."
            
            yield f"data: {json.dumps({'reply': final_reply, 'is_verified': True})}\n\n"

        # --- D. Check contract balance (dynamic DB) ---
        elif intent_name in ["check_balance", "check_certificate"]:
            print(f"[CHAT-HANDLER] check_balance/check_certificate extracted_id={extracted_id}")
            # Filler first — serve pre-built MP3 URL (0 ms, no edge-tts call)
            filler_url = random.choice(FILLER_URLS.get(intent_name, FILLER_URLS["check_balance"]))
            yield f"data: {json.dumps({'filler_url': filler_url})}\n\n"

            if extracted_id:
                final_reply = get_contract_info(extracted_id)
            else:
                final_reply = "Гэрээний дугаараа хэлнэ үү. Би мэдээллийг тань шалгаад өгье."
            
            yield f"data: {json.dumps({'reply': final_reply, 'is_verified': True})}\n\n"

        # --- E. GPT Stream (RAG & General Chat) ---
        else:
            print(f"[CHAT-HANDLER] gpt_stream intent={intent_name}")
            # Filler first for slow intents — serve pre-built MP3 URL (0 ms)
            filler_url = random.choice(FILLER_URLS.get(intent_name) or FILLER_URLS["general_chat"])
            yield f"data: {json.dumps({'filler_url': filler_url})}\n\n"

            sys_msg = "You are 'Mongol AI', an intelligent assistant for a Mongolian insurance company. Reply concisely, clearly, and politely. Always respond in Mongolian."

            # Add RAG context if PDF search is needed
            if intent_name == "rag_search":
                rag_context, sources = search_knowledge_base(user_input)
                if rag_context:
                    sys_msg += f"\n\nAnswer based on the following document excerpts:\n{rag_context}"
                    source = ", ".join(sources) if sources else None
                    print(f"[CHAT-HANDLER] rag_search with context source={source}")
                else:
                    print("[CHAT-HANDLER] rag_search no context found")

            messages_for_gpt = [{"role": "system", "content": sys_msg}] + history + [{"role": "user", "content": user_input}]

            try:
                response = client.chat.completions.create(
                    model=CHAT_MODEL,
                    messages=messages_for_gpt,
                    stream=True,
                    temperature=0
                )
                
                for chunk in response:
                    if chunk.choices and chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        final_reply += content
                        # Send each chunk to the frontend
                        yield f"data: {json.dumps({'reply': content, 'is_verified': False})}\n\n"

            except Exception as e:
                final_reply = f"A temporary system error occurred: {str(e)}"
                yield f"data: {json.dumps({'reply': final_reply})}\n\n"

        # --- 5. Save conversation history (last 10 messages) ---
        if final_reply:
            history.append({"role": "user", "content": user_input})
            history.append({"role": "assistant", "content": final_reply})
            state_obj.history = history[-10:]
            state_obj.save()

    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')


@api.post("/tts")
def tts_endpoint(request, payload: TTSRequest):
    text = (payload.text or "").strip()
    if not text:
        return JsonResponse({"error": "Text is required."}, status=400)

    audio_data, content_type = text_to_speech(text)
    if not audio_data:
        return JsonResponse({"error": "TTS returned no audio."}, status=500)

    return HttpResponse(audio_data, content_type=content_type or "audio/wav")


async def _edge_tts_async_gen(text: str, voice: str):
    """Pure async generator — no event loop creation, runs concurrently per request."""
    communicate = edge_tts.Communicate(text, voice, rate="+0%")
    async for chunk in communicate.stream():
        if chunk.get("type") == "audio":
            data = chunk.get("data", b"")
            if data:
                yield data


def _build_tts_stream_response(text: str):
    """Sync fallback (WSGI). Kept for internal /tts endpoint usage."""
    text = (text or "").strip()
    if not text:
        return JsonResponse({"error": "Text is required."}, status=400)

    voice = os.getenv("EDGE_TTS_VOICE", "mn-MN-YesuiNeural")

    try:
        response = StreamingHttpResponse(
            _edge_tts_stream_chunks(text, voice),
            content_type="audio/mpeg",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
    except Exception as e:
        print(f"[TTS][ERROR] Streaming endpoint exception: {e}")
        return JsonResponse({"error": "TTS streaming failed."}, status=500)


@api.get("/tts-stream")
async def tts_stream_endpoint(request, text: str = ""):
    """Async GET endpoint — multiple requests run concurrently in the ASGI event loop."""
    text = (text or "").strip()
    if not text:
        return JsonResponse({"error": "Text is required."}, status=400)
    voice = os.getenv("EDGE_TTS_VOICE", "mn-MN-YesuiNeural")
    try:
        response = StreamingHttpResponse(
            _edge_tts_async_gen(text, voice),
            content_type="audio/mpeg",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
    except Exception as e:
        print(f"[TTS][ERROR] async stream GET exception: {e}")
        return JsonResponse({"error": "TTS streaming failed."}, status=500)


@api.post("/tts-stream")
async def tts_stream_post_endpoint(request, payload: TTSRequest):
    """Async POST endpoint — concurrent with other TTS requests, no thread blocking."""
    text = (payload.text or "").strip()
    if not text:
        return JsonResponse({"error": "Text is required."}, status=400)
    voice = os.getenv("EDGE_TTS_VOICE", "mn-MN-YesuiNeural")
    try:
        response = StreamingHttpResponse(
            _edge_tts_async_gen(text, voice),
            content_type="audio/mpeg",
        )
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"
        return response
    except Exception as e:
        print(f"[TTS][ERROR] async stream POST exception: {e}")
        return JsonResponse({"error": "TTS streaming failed."}, status=500)


# ==========================================
# 3. PDF TRAINING
# ==========================================
@api.post("/train-from-pdf")
def train_from_pdf(request, file: UploadedFile = File(...)):
    """
    Read a PDF and extract intents and static answers to store in the database.
    """
    try:
        # 1. Extract text from PDF
        pdf_text = ""
        with pdfplumber.open(io.BytesIO(file.read())) as pdf:
            for page in pdf.pages:
                pdf_text += (page.extract_text() or "") + "\n"

        if not pdf_text.strip():
            return {"success": False, "error": "Could not extract text from the PDF."}

        # 2. Parse intents and answers from text using GPT
        prompt = f"""
        You are an Insurance Data Engineer. From the text below, extract the key questions a user might ask
        as 'intents' and their corresponding answers.

        Reply ONLY in the following JSON format:
        {{
            "data": [
                {{
                    "intent_name": "reinsurance_def",
                    "answer": "Detailed answer here...",
                    "alternative_queries": ["what is reinsurance", "reinsurance meaning", "reinsurance гэж юу вэ"]
                }}
            ]
        }}

        TEXT:
        {pdf_text[:6000]}
        """

        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )

        raw_content = response.choices[0].message.content.strip()
        if raw_content.startswith("```"):
            raw_content = raw_content.strip("`")
            if raw_content.lower().startswith("json"):
                raw_content = raw_content[4:].strip()

        extracted_data = json.loads(raw_content).get("data", [])

        # 3. Save results to PostgreSQL
        created_count = 0
        for item in extracted_data:
            intent_obj, _ = Intent.objects.get_or_create(intent_name=item['intent_name'])

            IntentDetail.objects.create(
                intent=intent_obj,
                answer=item['answer'],
                alternative_intent=item.get('alternative_queries', []),
                source_pdf=file.name
            )
            created_count += 1

        return {
            "success": True,
            "message": f"Success! {created_count} new rules extracted from PDF and saved to database.",
            "extracted": extracted_data
        }

    except Exception as e:
        print(f"Error training PDF: {e}")
        return {"success": False, "error": str(e)}