"""
Voice services — Salus
ASR: Boson Higgs Audio Understanding v3.5
TTS: Eigen Higgs 2.5

THE FIX: httpx data={} sends application/x-www-form-urlencoded.
Eigen /generate requires multipart/form-data.
Use files={} in httpx to force multipart — even for non-file fields.
"""
import httpx
import os
import io
import base64
import soundfile as sf
import numpy as np
import torch
import torchaudio
from openai import AsyncOpenAI
import traceback

BOSONAI_API_KEY = os.environ.get("BOSONAI_API_KEY", "")
EIGEN_API_KEY   = os.environ.get("EIGEN_API_KEY", "")

BOSON_BASE_URL       = "https://hackathon.boson.ai/v1"
BOSON_MODEL          = "higgs-audio-understanding-v3.5-Hackathon"
BOSON_MODEL_FALLBACK = "higgs-audio-understanding-v3-Hackathon"
EIGEN_TTS_URL        = "https://api-web.eigenai.com/api/v1/generate"

STOP_SEQUENCES = [
    "<|eot_id|>", "<|endoftext|>", "<|audio_eos|>", "<|im_end|>"
]

boson_client = AsyncOpenAI(
    api_key=BOSONAI_API_KEY,
    base_url=BOSON_BASE_URL,
    timeout=60.0,
)


# ── ASR helpers ───────────────────────────────────────────────────────────────

async def chunk_audio_for_boson(wav_bytes: bytes) -> list[str]:
    """Load WAV, mono-mix, resample to 16 kHz, split into ≤4 s b64 chunks."""
    buf = io.BytesIO(wav_bytes)
    waveform, sr = torchaudio.load(buf)

    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)

    target_sr = 16000
    if sr != target_sr:
        waveform = torchaudio.transforms.Resample(sr, target_sr)(waveform)

    wav_mono    = waveform[0]
    max_samples = 4 * target_sr
    chunks: list[str] = []
    start = 0

    while start < len(wav_mono):
        end   = min(start + max_samples, len(wav_mono))
        chunk = wav_mono[start:end]
        if len(chunk) < 1600:
            chunk = torch.nn.functional.pad(chunk, (0, 1600 - len(chunk)))
        c_int16 = (chunk * 32767.0).clamp(-32768, 32767).numpy().astype(np.int16)
        chunk_buf = io.BytesIO()
        sf.write(chunk_buf, c_int16, target_sr, format="WAV", subtype="PCM_16")
        chunks.append(base64.b64encode(chunk_buf.getvalue()).decode("utf-8"))
        start = end

    return chunks


async def transcribe_eigen_asr(wav_bytes: bytes, language: str | None = None) -> str:
    """Transcribe WAV using Boson Higgs Audio Understanding v3.5."""
    try:
        chunks = await chunk_audio_for_boson(wav_bytes)
        print(f"[ASR] {len(chunks)} chunk(s) → Boson")

        audio_parts = [
            {"type": "audio_url", "audio_url": {"url": f"data:audio/wav_{i};base64,{b64}"}}
            for i, b64 in enumerate(chunks)
        ]

        system_msg = (
            "You are an ASR system for emergency 911 calls. "
            "Transcribe speech accurately even through panic, crying, or noise. "
            "Output ONLY the spoken words as plain text."
        )
        user_text = "Transcribe the audio exactly as spoken."
        if language:
            user_text += f" Language: {language}."

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": [{"type": "text", "text": user_text}] + audio_parts},
        ]

        for model in [BOSON_MODEL, BOSON_MODEL_FALLBACK]:
            try:
                resp = await boson_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    stop=STOP_SEQUENCES,
                    extra_body={"skip_special_tokens": False},
                    temperature=0.2,
                    top_p=0.9,
                    max_tokens=2048,
                )
                result = (resp.choices[0].message.content or "").strip()
                print(f"[ASR] transcript: {result[:120]}")
                return result
            except Exception as e:
                print(f"[ASR] {model} failed: {e}")
                continue

        return ""

    except Exception as e:
        traceback.print_exc()
        print(f"[ASR] fatal: {e}")
        return ""


# ── TTS ───────────────────────────────────────────────────────────────────────

def build_tts_text(text: str, emotion: str | None) -> str:
    if emotion in ("urgent", "serious"):
        return f"<|higher_expressiveness|> [{emotion}] {text}"
    if emotion:
        return f"[{emotion}] {text}"
    return text


async def synthesize_dispatcher_voice(
    text: str,
    voice: str = "Linda",
    emotion: str | None = None,
    temperature: float = 0.5,
) -> bytes | None:
    """
    Synthesize speech via Eigen Higgs 2.5.

    CRITICAL: Eigen /generate requires multipart/form-data.
    httpx files={} sends proper multipart even for plain text fields.
    httpx data={} sends application/x-www-form-urlencoded — WRONG, returns error.
    """
    if not text or not text.strip():
        return None

    tts_text = build_tts_text(text, emotion)
    print(f"[TTS] synthesize | voice={voice} emotion={emotion} | {tts_text[:80]}")

    # Build multipart payload using httpx files= (forces multipart/form-data)
    # Each field: (filename, value, content-type) — use None filename for plain fields
    multipart = {
        "model":       (None, "higgs2p5"),
        "text":        (None, tts_text),
        "voice":       (None, voice),
        "stream":      (None, "false"),
        "temperature": (None, str(temperature)),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                EIGEN_TTS_URL,
                headers={"Authorization": f"Bearer {EIGEN_API_KEY}"},
                files=multipart,
            )
            print(f"[TTS] status={resp.status_code} bytes={len(resp.content)}")

            if resp.status_code != 200:
                print(f"[TTS] error body: {resp.text[:400]}")
                return None

            if len(resp.content) < 200:
                print(f"[TTS] suspiciously small response ({len(resp.content)} bytes): {resp.text[:200]}")
                return None

            # Sanity check: valid audio starts with RIFF (WAV) or ID3/0xFF (MP3)
            magic = resp.content[:4]
            if not (magic[:4] == b'RIFF' or magic[0] == 0xFF or magic[:3] == b'ID3'):
                print(f"[TTS] unexpected magic bytes: {magic.hex()} — response: {resp.text[:200]}")
                return None

            print(f"[TTS] audio OK — {len(resp.content)} bytes, magic={magic.hex()}")
            return resp.content

        except Exception as e:
            traceback.print_exc()
            print(f"[TTS] request failed: {e}")
            return None


async def synthesize_dispatcher_voice_stream(
    text: str,
    voice: str = "Linda",
    emotion: str | None = None,
    temperature: float = 0.5,
):
    """
    Streaming TTS — yields audio chunks as they arrive.
    Falls back to full synthesis if streaming fails/times out.
    """
    if not text or not text.strip():
        return

    tts_text = build_tts_text(text, emotion)
    print(f"[TTS-STREAM] {tts_text[:80]}")

    multipart = {
        "model":       (None, "higgs2p5"),
        "text":        (None, tts_text),
        "voice":       (None, voice),
        "stream":      (None, "true"),
        "temperature": (None, str(temperature)),
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                EIGEN_TTS_URL,
                headers={"Authorization": f"Bearer {EIGEN_API_KEY}"},
                files=multipart,
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    print(f"[TTS-STREAM] HTTP {resp.status_code}: {body[:300]}")
                    # Fall back to non-streaming
                    audio = await synthesize_dispatcher_voice(text, voice, emotion, temperature)
                    if audio:
                        yield audio
                    return

                print("[TTS-STREAM] streaming started")
                async for chunk in resp.aiter_bytes(8192):
                    if chunk:
                        yield chunk

    except Exception as e:
        traceback.print_exc()
        print(f"[TTS-STREAM] error: {e} — falling back")
        audio = await synthesize_dispatcher_voice(text, voice, emotion, temperature)
        if audio:
            yield audio
