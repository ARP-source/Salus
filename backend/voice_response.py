"""
Voice services — Salus
ASR: Eigen higgs_asr_3  (fast dedicated ASR — replaces slow Boson multimodal path)
TTS: Eigen Higgs 2.5

THE FIX: httpx data={} sends application/x-www-form-urlencoded.
Eigen /generate requires multipart/form-data.
Use files={} in httpx to force multipart — even for non-file fields.
"""
import httpx
import os
import traceback

EIGEN_API_KEY  = os.environ.get("EIGEN_API_KEY", "")

EIGEN_BASE_URL = "https://api-web.eigenai.com/api/v1"
EIGEN_GEN_URL  = f"{EIGEN_BASE_URL}/generate"  # Used for both ASR and TTS


# ── ASR ───────────────────────────────────────────────────────────────────────

async def transcribe_eigen_asr(wav_bytes: bytes, language: str | None = None) -> str:
    """
    Transcribe WAV using Eigen higgs_asr_3.
    Uses the same /api/v1/generate endpoint as TTS.
    Eigen auto-resamples to 16kHz mono, so raw WAV bytes go straight through.
    """
    try:
        print(f"[ASR] {len(wav_bytes)} bytes → Eigen higgs_asr_3")

        # higgs_asr_3 uses /generate with: model + file + optional language
        fields: dict = {
            "model": (None, "higgs_asr_3"),
        }
        if language:
            fields["language"] = (None, language)

        # audio file field name is "file" per Eigen docs
        fields["file"] = ("audio.wav", wav_bytes, "audio/wav")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                EIGEN_GEN_URL,
                headers={"Authorization": f"Bearer {EIGEN_API_KEY}"},
                files=fields,
            )

        print(f"[ASR] status={resp.status_code}")

        if resp.status_code != 200:
            print(f"[ASR] error body: {resp.text[:400]}")
            return ""

        # Response is plain text transcript
        result = resp.text.strip()
        print(f"[ASR] transcript: {result[:120]}")
        return result

    except Exception as e:
        traceback.print_exc()
        print(f"[ASR] fatal: {e}")
        return ""


# ── TTS ───────────────────────────────────────────────────────────────────────

def build_tts_text(text: str, emotion: str | None) -> str:
    # Do NOT inject text tags — Higgs 2.5 reads them aloud literally.
    # Expressiveness is controlled via the temperature parameter only.
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
    print(f"[TTS] synthesize | voice={voice} emotion={emotion} temp={temperature} | {tts_text[:80]}")

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
                EIGEN_GEN_URL,
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

            print(f"[TTS] audio OK — {len(resp.content)} bytes, magic={magic.hex()}, first50={resp.content[:50]}")
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
                EIGEN_GEN_URL,
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
                first_chunk = True
                async for chunk in resp.aiter_bytes(8192):
                    if chunk:
                        if first_chunk:
                            print(f"[TTS-STREAM] first chunk: {len(chunk)} bytes, magic={chunk[:4].hex()}")
                            first_chunk = False
                        yield chunk

    except Exception as e:
        traceback.print_exc()
        print(f"[TTS-STREAM] error: {e} — falling back")
        audio = await synthesize_dispatcher_voice(text, voice, emotion, temperature)
        if audio:
            yield audio
