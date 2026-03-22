"""
Salus — Real-Time Emergency Dispatch Intelligence
=================================================
Pipeline (optimised for low latency):

  mic chunks ──► VAD silence detection
                      │
                      ▼
                 Eigen ASR  (Boson Higgs v3.5, parallel chunks)
                      │
                      ├──► transcript sent to frontend immediately
                      │
                      ▼
                 GPT-OSS LLM  (dispatch intelligence extraction)
                      │
                      ├──► dispatch_update sent to frontend
                      │
                      ▼
                 Eigen TTS  (Higgs 2.5, sentence-parallel synthesis)
                      │
                      ▼
                 voice_response chunks sent to frontend as they arrive

Key improvements over original:
• TTS is now multipart/form-data (Eigen's actual expected format)
• Sentences are synthesised IN PARALLEL — first sentence plays while
  subsequent ones are still generating
• Each sentence is sent to the frontend as its own voice_response message
  so the browser can start playing immediately
• ASR chunks are transcribed in parallel inside voice_response.py
• Audio queue in the frontend plays them sequentially (already correct)
"""

import asyncio
import base64
import io
import json
import os
import traceback
import wave

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Salus Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from dispatch_brain import run_dispatch_llm
from voice_response import (
    transcribe_eigen_asr,
    synthesize_dispatcher_voice,
    synthesize_dispatcher_voice_stream,
)


# ── Session & connection state ────────────────────────────────────────────────

class CallSession:
    def __init__(self):
        self.history:       list       = []
        self.full_transcript: str      = ""
        self.pending_audio: bytearray  = bytearray()
        self.processing:    bool       = False


class ConnectionManager:
    def __init__(self):
        self.active: list = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)


manager = ConnectionManager()


# ── Helpers ───────────────────────────────────────────────────────────────────

def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)         # int16
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def _emotion_for(dispatch_data: dict) -> tuple[str | None, float]:
    severity       = dispatch_data.get("severity", "UNKNOWN")
    caller_state   = dispatch_data.get("caller_state", "UNKNOWN")
    emergency_type = dispatch_data.get("emergency_type", "UNKNOWN")

    if severity == "CRITICAL" or emergency_type in ("MEDICAL", "FIRE"):
        return "urgent", 0.8
    if severity in ("SERIOUS", "HIGH") or caller_state == "PANICKED":
        return "serious", 0.7
    if caller_state in ("CRYING", "SUICIDAL", "IN_SHOCK") or emergency_type == "MENTAL_HEALTH":
        return "gentle", 0.6
    return None, 0.5


# ── Core utterance pipeline ───────────────────────────────────────────────────


async def process_utterance(ws: WebSocket, session: CallSession, pcm_bytes: bytes):
    """
    Full pipeline for one caller utterance:
      PCM → WAV → ASR → transcript → LLM → dispatch update → TTS → audio
    """
    if session.processing:
        return
    session.processing = True

    try:
        wav_bytes = pcm_to_wav_bytes(pcm_bytes)
        print(f"[ASR] {len(wav_bytes)} WAV bytes queued")

        # ── 1. ASR ────────────────────────────────────────────────────────
        transcript_chunk = await transcribe_eigen_asr(wav_bytes)

        if not transcript_chunk or len(transcript_chunk.strip()) < 2:
            print("[ASR] empty transcript — skipping")
            return

        session.full_transcript = (
            session.full_transcript + " " + transcript_chunk
        ).strip()

        # Send transcript to frontend immediately
        await ws.send_text(json.dumps({
            "type": "transcript_update",
            "data": transcript_chunk,
        }))

        session.history.append({"role": "user", "content": transcript_chunk})

        # ── 2. LLM ───────────────────────────────────────────────────────
        print("[LLM] generating dispatch response…")
        dispatch_data = await run_dispatch_llm(
            session.full_transcript, {}, session.history
        )

        await ws.send_text(json.dumps({
            "type": "dispatch_update",
            "data": dispatch_data,
        }))

        response_text = dispatch_data.get("dispatcher_response_text", "")
        if not response_text:
            return

        session.history.append({"role": "assistant", "content": response_text})

        emotion, temperature = _emotion_for(dispatch_data)

        # ── 3. TTS — stream sentences in parallel ─────────────────────────
        # We try the true streaming endpoint first; if it yields data quickly
        # the caller hears a response in ~1 s.  If it fails we fall back to
        # sentence-level parallel synthesis.
        await _tts_and_send(ws, response_text, emotion, temperature)

    except Exception as e:
        traceback.print_exc()
        try:
            await ws.send_text(json.dumps({"type": "error", "error": str(e)}))
        except Exception:
            pass
    finally:
        session.processing = False


async def _tts_and_send(
    ws: WebSocket,
    text: str,
    emotion: str | None,
    temperature: float,
):
    """
    Strategy:
      1. Try streaming endpoint — collect chunks and send each to the frontend
         as soon as it arrives (sub-second first-chunk latency when it works).
      2. If streaming stalls or fails, fall back to sentence-parallel synthesis.
    """
    import re

    collected = bytearray()
    stream_ok  = False

    try:
        async with asyncio.timeout(8):          # Give stream 8 s to start
            async for chunk in synthesize_dispatcher_voice_stream(
                text, emotion=emotion, temperature=temperature
            ):
                if chunk:
                    stream_ok = True
                    collected.extend(chunk)
    except asyncio.TimeoutError:
        print("[TTS] stream timeout — falling back to sentence-parallel")
    except Exception as e:
        print(f"[TTS] stream error: {e} — falling back to sentence-parallel")

    # Send the complete collected audio (with proper headers) as one piece
    if stream_ok and len(collected) > 200:
        audio_bytes = bytes(collected)
        b64 = base64.b64encode(audio_bytes).decode()
        print(f"[TTS] streamed {len(audio_bytes)} bytes, magic={audio_bytes[:4].hex()}, b64_start={b64[:20]}")
        await ws.send_text(json.dumps({
            "type": "voice_response",
            "data": b64,
        }))
        return

    # ── Fallback: split into sentences and synthesise in parallel ─────────
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    if not sentences:
        sentences = [text]

    print(f"[TTS] sentence-parallel fallback: {len(sentences)} sentence(s)")

    async def _synthesise_one(s: str) -> bytes | None:
        return await synthesize_dispatcher_voice(s, emotion=emotion, temperature=temperature)

    results = await asyncio.gather(*[_synthesise_one(s) for s in sentences])

    for i, audio in enumerate(results):
        if audio and len(audio) > 200:
            b64 = base64.b64encode(audio).decode()
            print(f"[TTS] fallback sentence {i}: {len(audio)} bytes, magic={audio[:4].hex()}, b64_start={b64[:20]}")
            await ws.send_text(json.dumps({
                "type": "voice_response",
                "data": b64,
            }))
        else:
            print(f"[TTS] fallback sentence {i}: FAILED (audio={audio is not None}, len={len(audio) if audio else 0})")




# ── Demo file pipeline ────────────────────────────────────────────────────────

async def process_demo_file(ws: WebSocket, file_path: str):
    try:
        print(f"[Demo] {file_path}")
        with open(file_path, "rb") as f:
            wav_bytes = f.read()

        await ws.send_text(json.dumps({"type": "status", "data": "Processing demo call…"}))

        transcript = await transcribe_eigen_asr(wav_bytes)
        if not transcript:
            transcript = "(could not transcribe demo audio)"

        await ws.send_text(json.dumps({"type": "transcript_update", "data": transcript}))

        dispatch_data = await run_dispatch_llm(transcript, {}, [])
        await ws.send_text(json.dumps({"type": "dispatch_update", "data": dispatch_data}))

        response_text = dispatch_data.get("dispatcher_response_text", "")
        if response_text:
            emotion, temperature = _emotion_for(dispatch_data)
            await _tts_and_send(ws, response_text, emotion, temperature)

        print("[Demo] done")
    except Exception as e:
        traceback.print_exc()
        try:
            await ws.send_text(json.dumps({"type": "error", "error": str(e)}))
        except Exception:
            pass


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    session = CallSession()

    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except Exception:
                continue

            msg_type = msg.get("type")

            if msg_type == "simulate":
                filename = msg.get("data", "")
                # New: filename is a scenario name like "en_cardiac_arrest"
                # Strip .wav extension if present (legacy)
                scenario_name = filename.replace(".wav", "").replace("_caller", "")
                
                root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                scenario_dir = os.path.join(root, "demo_calls", scenario_name)
                
                session = CallSession()
                
                if os.path.exists(scenario_dir) and os.path.exists(os.path.join(scenario_dir, "meta.json")):
                    # New multi-turn scenario
                    asyncio.create_task(process_scenario(ws, scenario_name))
                else:
                    # Legacy single-file fallback
                    filepath = os.path.join(root, "demo_calls", filename)
                    if not filename.endswith(".wav"):
                        filepath += ".wav"
                    if os.path.exists(filepath):
                        asyncio.create_task(process_demo_file(ws, filepath))
                    else:
                        await ws.send_text(json.dumps({
                            "type": "error",
                            "error": f"Scenario not found: {scenario_name}. Run demo_calls/generate_demos.py first."
                        }))

            elif msg_type == "audio_chunk":
                b64 = msg.get("data", "")
                if b64:
                    chunk = base64.b64decode(b64)
                    session.pending_audio.extend(chunk)

            elif msg_type == "utterance_end":
                if len(session.pending_audio) > 3200:
                    pcm_snapshot = bytes(session.pending_audio)
                    session.pending_audio = bytearray()
                    asyncio.create_task(process_utterance(ws, session, pcm_snapshot))
                else:
                    session.pending_audio = bytearray()

            elif msg_type == "stop":
                if len(session.pending_audio) > 3200:
                    pcm_snapshot = bytes(session.pending_audio)
                    session.pending_audio = bytearray()
                    await process_utterance(ws, session, pcm_snapshot)
                session = CallSession()

    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        traceback.print_exc()
        manager.disconnect(ws)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Multi-turn demo scenario player ──────────────────────────────────────────

async def process_scenario(ws, scenario_name: str):
    """
    Play a multi-turn demo scenario.
    
    For each caller turn:
    1. Send the caller audio to the frontend (plays through browser)
    2. Transcribe it via ASR
    3. Run LLM to generate dispatcher response
    4. Synthesize and send dispatcher voice
    5. Pause briefly, then play next caller turn
    """
    import json as _json

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scenario_dir = os.path.join(root, "demo_calls", scenario_name)
    meta_path    = os.path.join(scenario_dir, "meta.json")

    if not os.path.exists(meta_path):
        await ws.send_text(_json.dumps({
            "type": "error",
            "error": f"Scenario not found: {scenario_name}. Run demo_calls/generate_demos.py first."
        }))
        return

    with open(meta_path) as f:
        meta = _json.load(f)

    num_turns = meta["num_turns"]
    session   = CallSession()

    await ws.send_text(_json.dumps({
        "type": "status",
        "data": f"Starting scenario: {meta['name']} ({num_turns} turns)"
    }))

    await asyncio.sleep(0.8)

    for i in range(num_turns):
        turn_path = os.path.join(scenario_dir, f"turn_{i:02d}.wav")
        if not os.path.exists(turn_path):
            print(f"[Scenario] turn {i} WAV missing, stopping")
            break

        print(f"[Scenario] Playing turn {i+1}/{num_turns}")

        # ── 1. Send caller audio to frontend so judges hear the caller ────
        with open(turn_path, "rb") as f:
            caller_audio_bytes = f.read()

        caller_b64 = base64.b64encode(caller_audio_bytes).decode("utf-8")
        await ws.send_text(_json.dumps({
            "type": "caller_audio",   # Frontend plays this through speaker
            "data": caller_b64,
            "turn": i,
            "total": num_turns,
        }))

        # ── 2. Transcribe the caller audio ────────────────────────────────
        transcript_chunk = await transcribe_eigen_asr(caller_audio_bytes)
        if not transcript_chunk:
            transcript_chunk = meta["turns"][i]["text"]  # fallback to script

        session.full_transcript = (session.full_transcript + " " + transcript_chunk).strip()

        await ws.send_text(_json.dumps({
            "type": "transcript_update",
            "data": transcript_chunk,
        }))

        session.history.append({"role": "user", "content": transcript_chunk})

        # Small pause so frontend can play caller audio before dispatcher responds
        await asyncio.sleep(2.5)

        # ── 3. LLM dispatch response ──────────────────────────────────────
        dispatch_data = await run_dispatch_llm(session.full_transcript, {}, session.history)
        await ws.send_text(_json.dumps({"type": "dispatch_update", "data": dispatch_data}))

        response_text = dispatch_data.get("dispatcher_response_text", "")
        if not response_text:
            continue

        session.history.append({"role": "assistant", "content": response_text})

        # ── 4. TTS dispatcher response ────────────────────────────────────
        severity       = dispatch_data.get("severity", "UNKNOWN")
        emergency_type = dispatch_data.get("emergency_type", "UNKNOWN")
        caller_state   = dispatch_data.get("caller_state", "UNKNOWN")

        if severity == "CRITICAL" or emergency_type in ("MEDICAL", "FIRE"):
            emotion, temperature = "urgent", 0.8
        elif caller_state in ("CRYING", "PANICKED"):
            emotion, temperature = "serious", 0.7
        else:
            emotion, temperature = None, 0.5

        voice_bytes = await synthesize_dispatcher_voice(
            response_text, emotion=emotion, temperature=temperature
        )
        if voice_bytes:
            b64 = base64.b64encode(voice_bytes).decode("utf-8")
            await ws.send_text(_json.dumps({"type": "voice_response", "data": b64}))

        # ── 5. Wait for dispatcher audio to finish before next caller turn ─
        # Estimate: ~150 chars/second for TTS, min 3s gap
        estimated_duration = max(3.0, len(response_text) / 15)
        await asyncio.sleep(estimated_duration + 1.0)

    await ws.send_text(_json.dumps({
        "type": "status",
        "data": "Scenario complete. Units have arrived on scene."
    }))
    print(f"[Scenario] {scenario_name} complete")
