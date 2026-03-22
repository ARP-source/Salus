"""
Eigen AI voice services.
- ASR: higgs_asr_3 via POST /api/v1/generate (multipart, file upload)
- TTS: higgs2p5   via POST /api/v1/generate (multipart, text param)
Both use the same /generate endpoint with different model + params.
"""
import httpx
import os
import json

EIGEN_API_KEY = os.environ.get("EIGEN_API_KEY", "")
EIGEN_BASE = "https://api-web.eigenai.com/api/v1"


async def transcribe_eigen_asr(audio_bytes: bytes, language: str = None) -> str:
    """
    Transcribe audio using Eigen higgs_asr_3.
    Sends WAV bytes as multipart form to /generate.
    Returns transcribed text string.
    """
    data = {"model": "higgs_asr_3"}
    if language:
        data["language"] = language

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{EIGEN_BASE}/generate",
                headers={"Authorization": f"Bearer {EIGEN_API_KEY}"},
                data=data,
                files={"file": ("audio.wav", audio_bytes, "audio/wav")},
            )
            print(f"[ASR] Status: {response.status_code}")
            if response.status_code != 200:
                print(f"[ASR] Error body: {response.text[:500]}")
                return ""
            
            # Try JSON parse first
            try:
                res = response.json()
                print(f"[ASR] JSON response: {str(res)[:200]}")
                if isinstance(res, dict):
                    return (
                        res.get("text") or
                        res.get("transcript") or
                        res.get("result") or
                        res.get("data", {}).get("text", "") or
                        ""
                    )
                if isinstance(res, str):
                    return res
                return str(res)
            except Exception:
                # Plain text response
                text = response.text.strip()
                print(f"[ASR] Text response: {text[:200]}")
                return text

    except Exception as e:
        print(f"[ASR] Exception: {type(e).__name__}: {e}")
        return ""


async def synthesize_dispatcher_voice(
    text: str,
    voice: str = "Linda",
    speed: float = 0.9
) -> bytes | None:
    """
    Synthesize speech using Eigen higgs2p5.
    Returns raw audio bytes (WAV).
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{EIGEN_BASE}/generate",
                headers={"Authorization": f"Bearer {EIGEN_API_KEY}"},
                data={
                    "model": "higgs2p5",
                    "text": text,
                    "voice": voice,
                    "stream": "false",
                    "sampling": json.dumps({
                        "temperature": 0.85,
                        "top_p": 0.95,
                        "top_k": 50,
                    }),
                    "voice_settings": json.dumps({
                        "speed": speed,
                    }),
                },
            )
            print(f"[TTS] Status: {response.status_code}, bytes: {len(response.content)}")
            if response.status_code != 200:
                print(f"[TTS] Error body: {response.text[:300]}")
                return None
            if len(response.content) < 100:
                print(f"[TTS] Suspiciously small response: {response.text[:200]}")
                return None
            return response.content

    except Exception as e:
        print(f"[TTS] Exception: {type(e).__name__}: {e}")
        return None
