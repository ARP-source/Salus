"""
Voice services:
- ASR: Boson Higgs Audio Understanding v3.5 (hackathon.boson.ai)
- TTS: Eigen Higgs 2.5 (api-web.eigenai.com)
"""
import httpx
import os
import io
import base64
import json
import tempfile
import soundfile as sf
import numpy as np
import torch
import torchaudio
from openai import AsyncOpenAI

BOSONAI_API_KEY = os.environ.get("BOSONAI_API_KEY", "")
EIGEN_API_KEY = os.environ.get("EIGEN_API_KEY", "")

# Boson API for Higgs Audio Understanding (ASR)
BOSON_BASE_URL = "https://hackathon.boson.ai/v1"
BOSON_MODEL = "higgs-audio-understanding-v3.5-Hackathon"
BOSON_MODEL_FALLBACK = "higgs-audio-understanding-v3-Hackathon"

# Eigen API for TTS
EIGEN_BASE = "https://api-web.eigenai.com/api/v1"

# Boson client (OpenAI-compatible)
boson_client = AsyncOpenAI(
    api_key=BOSONAI_API_KEY,
    base_url=BOSON_BASE_URL,
    timeout=60.0,
)

# Stop sequences required by Boson API
STOP_SEQUENCES = ["<" + "|eot_id|" + ">", "<" + "|endoftext|" + ">", "<" + "|audio_eos|" + ">", "<" + "|im_end|" + ">"]


async def chunk_audio_for_boson(wav_bytes: bytes) -> list:
    """
    Chunk audio into max 4-second segments as required by Boson API.
    Returns list of base64-encoded WAV chunks.
    """
    buf = io.BytesIO(wav_bytes)
    waveform, sr = torchaudio.load(buf)
    
    # Mix to mono
    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)
    
    # Resample to 16kHz (required by API)
    target_sr = 16000
    if sr != target_sr:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=target_sr)
        waveform = resampler(waveform)
    
    wav_mono = waveform[0]
    total_samples = len(wav_mono)
    max_samples = 4 * target_sr  # 4 seconds max per chunk
    
    chunks = []
    start = 0
    while start < total_samples:
        end = min(start + max_samples, total_samples)
        chunk_wav = wav_mono[start:end]
        
        # Pad if too short
        if len(chunk_wav) < 1600:
            chunk_wav = torch.nn.functional.pad(chunk_wav, (0, 1600 - len(chunk_wav)))
        
        # Convert to int16 PCM
        c_int16 = (chunk_wav * 32767.0).clamp(-32768, 32767).numpy().astype(np.int16)
        
        # Encode as WAV
        chunk_buf = io.BytesIO()
        sf.write(chunk_buf, c_int16, target_sr, format="WAV", subtype="PCM_16")
        b64 = base64.b64encode(chunk_buf.getvalue()).decode("utf-8")
        chunks.append(b64)
        start = end
    
    return chunks


async def transcribe_eigen_asr(wav_bytes: bytes, language: str = None) -> str:
    """
    Transcribe audio using Boson Higgs Audio Understanding v3.5.
    Uses OpenAI-compatible chat completions with audio_url content parts.
    """
    try:
        # Chunk audio into 4-second segments
        chunks = await chunk_audio_for_boson(wav_bytes)
        print(f"[ASR] Chunked audio into {len(chunks)} segments, calling Boson API...")
        
        # Build audio content parts with indexed MIME types
        audio_parts = []
        for i, b64 in enumerate(chunks):
            audio_parts.append({
                "type": "audio_url",
                "audio_url": {"url": f"data:audio/wav_{i};base64,{b64}"}
            })
        
        # System prompt for ASR optimized for emergency calls
        system_msg = (
            "You are an automatic speech recognition (ASR) system optimized for emergency 911 calls. "
            "You must accurately transcribe speech even when the caller is panicked, crying, breathing heavily, "
            "or speaking through noise. Output ONLY the exact spoken words as plain text. No commentary."
        )
        
        # User prompt
        user_text = "Your task is to listen to audio input and output the exact spoken words as plain text."
        if language:
            user_text += f" The language is {language}."
        
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": [{"type": "text", "text": user_text}] + audio_parts}
        ]
        
        # Try v3.5 first, fallback to v3
        for model in [BOSON_MODEL, BOSON_MODEL_FALLBACK]:
            try:
                print(f"[ASR] Calling Boson with model: {model}")
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
                print(f"[ASR] Got transcript: {result[:100]}...")
                return result
            except Exception as e:
                print(f"[ASR] Model {model} failed: {e}")
                continue
        
        return ""
        
    except Exception as e:
        print(f"[ASR] Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return ""


def build_tts_text(text: str, emotion: str = None) -> str:
    """Build TTS text with Higgs 2.5 emotion tags."""
    if emotion in ["urgent", "serious"]:
        return f"<|higher_expressiveness|> [{emotion}] {text}"
    elif emotion:
        return f"[{emotion}] {text}"
    return text


async def synthesize_dispatcher_voice_stream(
    text: str,
    voice: str = "Linda",
    emotion: str = None,
    temperature: float = 0.5
):
    """
    Stream TTS audio chunks using Eigen higgs2p5.
    Yields audio chunks as they arrive for low-latency playback.
    Uses multipart form data as per Eigen API docs.
    """
    if not text or not text.strip():
        print("[TTS] Empty text, skipping")
        return
    
    tts_text = build_tts_text(text, emotion)
        
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print(f"[TTS-STREAM] Calling Eigen API (emotion={emotion}, temp={temperature})")
            print(f"[TTS-STREAM] Text: {tts_text[:100]}...")
            
            # Use multipart form data (like curl -F) NOT JSON
            # Note: For proper multipart, we need to send files parameter
            form_data = {
                "model": (None, "higgs2p5"),
                "text": (None, tts_text),
                "voice": (None, voice),
                "stream": (None, "true"),
            }
            
            async with client.stream(
                "POST",
                f"{EIGEN_BASE}/generate",
                headers={
                    "Authorization": f"Bearer {EIGEN_API_KEY}",
                },
                files=form_data,  # Multipart form data
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    print(f"[TTS-STREAM] Error {response.status_code}: {error_body[:300]}")
                    return
                
                print(f"[TTS-STREAM] Streaming started...")
                async for chunk in response.aiter_bytes(chunk_size=1024):
                    if chunk:
                        yield chunk
                        
                print(f"[TTS-STREAM] Streaming complete")

    except Exception as e:
        print(f"[TTS-STREAM] Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


async def synthesize_dispatcher_voice(
    text: str,
    voice: str = "Linda",
    emotion: str = None,
    temperature: float = 0.5
) -> bytes | None:
    """
    Synthesize speech using Eigen higgs2p5 (non-streaming fallback).
    """
    if not text or not text.strip():
        print("[TTS] Empty text, skipping")
        return None
    
    tts_text = build_tts_text(text, emotion)
        
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            print(f"[TTS] Calling Eigen API: {EIGEN_BASE}/generate (emotion={emotion}, temp={temperature})")
            print(f"[TTS] Text: {tts_text[:100]}...")
            
            payload = {
                "model": "higgs2p5",
                "text": tts_text,
                "voice": voice,
                "sampling": {
                    "temperature": temperature,
                    "top_p": 0.95,
                    "top_k": 50,
                },
            }
            
            response = await client.post(
                f"{EIGEN_BASE}/generate",
                headers={
                    "Authorization": f"Bearer {EIGEN_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            
            print(f"[TTS] Status: {response.status_code}, bytes: {len(response.content)}")
            
            if response.status_code != 200:
                print(f"[TTS] Error: {response.text[:500]}")
                return None
            
            if len(response.content) < 100:
                print(f"[TTS] Suspiciously small audio response")
                return None
            
            return response.content

    except Exception as e:
        print(f"[TTS] Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None
