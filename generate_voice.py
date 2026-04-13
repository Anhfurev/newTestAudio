"""
Pre-generate all filler phrase MP3 files into static/audio/.
Run once:  python generate_voice.py
"""
import asyncio
import os
import edge_tts

VOICE = "mn-MN-BataaNeural"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "static", "audio")

# key  → filename stem,  value → text to synthesise
FILLERS = {
    # check_balance / check_certificate
    "filler_balance_0": "За, би одоохон шалгаад хариу хэлье.",
    "filler_balance_1": "Ойлголоо, би яг одоо мэдээллийг тань хайж байна.",
    "filler_balance_2": "Гэрээний мэдээллийг системээс шүүж байна, түр хүлээнэ үү.",
    "filler_cert_0":    "За, би одоохон шалгаад хариу хэлье.",
    "filler_cert_1":    "Гэрчилгээний мэдээллийг системээс хайж байна, түр хүлээнэ үү.",
    # rag_search
    "filler_rag_0":     "Мэдээллийг тань баримт бичгээс хайж байна, түр хүлээнэ үү.",
    "filler_rag_1":     "Ойлголоо, би яг одоо баримт бичгээс хариулт олж байна.",
    "filler_rag_2":     "Холбогдох мэдээллийг шүүж байна, тун удахгүй хариулна.",
    # general_chat
    "filler_chat_0":    "Ойлголоо, бодоод хариулъя.",
    "filler_chat_1":    "За, тун удахгүй хариулна.",
}


async def generate(stem: str, text: str) -> None:
    path = os.path.join(OUTPUT_DIR, f"{stem}.mp3")
    communicate = edge_tts.Communicate(text, VOICE)
    await communicate.save(path)
    print(f"  ✅  {stem}.mp3  ({len(text)} chars)")


async def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating {len(FILLERS)} filler files → {OUTPUT_DIR}\n")
    await asyncio.gather(*(generate(stem, text) for stem, text in FILLERS.items()))
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())