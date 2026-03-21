import os
import json
from openai import AsyncOpenAI
from config import BOSONAI_API_KEY, BOSON_BASE_URL, BOSON_MODEL_PRIMARY, BOSON_MODEL_FALLBACK

boson_client = AsyncOpenAI(
    api_key=BOSONAI_API_KEY,
    base_url=BOSON_BASE_URL,
    timeout=180.0,
    max_retries=3,
)

async def call_boson(messages: list, max_tokens: int = 2048) -> str:
    for model in [BOSON_MODEL_PRIMARY, BOSON_MODEL_FALLBACK]:
        try:
            resp = await boson_client.chat.completions.create(
                model=model,
                messages=messages,
                stop=["<|eot_id|>", "<|endoftext|>", "<|audio_eos|>", "<|im_end|>"],
                extra_body={"skip_special_tokens": False},
                temperature=0.2,
                top_p=0.9,
                max_tokens=max_tokens,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"Boson call failed on {model}: {e}")
            continue
    return ""

async def call_boson_transcription(audio_chunks: list[str], language: str = None) -> str:
    # ASR Mode setup
    prompt = "Your task is to listen to audio input and output the exact spoken words as plain text."
    if language:
        prompt += f" in {language}."

    audio_parts = []
    for i, b64 in enumerate(audio_chunks):
        audio_parts.append({
            "type": "audio_url",
            "audio_url": {"url": f"data:audio/wav_{i};base64,{b64}"}
        })
    
    messages = [
        {"role": "system", "content": "You are an automatic speech recognition (ASR) system."},
        {"role": "user", "content": [{"type": "text", "text": prompt}] + audio_parts}
    ]
    return await call_boson(messages)
