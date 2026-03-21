import httpx
import os
import json

EIGEN_API_KEY = os.environ.get("EIGEN_API_KEY", "")

async def transcribe_eigen_asr(audio_bytes: bytes, language: str = None) -> str:
    data = {"model": "higgs_asr_3"}
    if language:
        data["language"] = language
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api-web.eigenai.com/api/v1/generate",
                headers={"Authorization": f"Bearer {EIGEN_API_KEY}"},
                data=data,
                files={"file": ("audio.wav", audio_bytes, "audio/wav")},
            )
            response.raise_for_status()
            # Depending on API format, it might return raw text or JSON
            res = response.json()
            if isinstance(res, dict) and 'text' in res:
                return res['text']
            return str(res)
    except Exception as e:
        print(f"Eigen ASR failed: {e}")
        return ""

async def synthesize_dispatcher_voice(text: str, voice: str = "Linda", speed: float = 0.9) -> bytes | None:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api-web.eigenai.com/api/v1/generate",
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
            response.raise_for_status()
            return response.content  # raw WAV bytes
    except Exception as e:
        print(f"Eigen synthesis failed: {e}")
        return None
