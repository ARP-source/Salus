"""
Salus - Real-Time Emergency Dispatch Intelligence
Pipeline: mic chunks → VAD silence detection → Eigen ASR → GPT-OSS LLM → Eigen TTS → audio back
The mic stays open the whole time for continuous conversation.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import base64
import os
import asyncio
import traceback
import io
import wave

app = FastAPI(title="Salus Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from dispatch_brain import run_dispatch_llm
from voice_response import synthesize_dispatcher_voice, transcribe_eigen_asr


class CallSession:
    def __init__(self):
        self.history: list = []
        self.full_transcript: str = ""
        self.pending_audio: bytearray = bytearray()
        self.processing = False


class ConnectionManager:
    def __init__(self):
        self.active: list = []

    async def connect(self, ws):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws):
        if ws in self.active:
            self.active.remove(ws)


manager = ConnectionManager()


def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


async def process_utterance(ws, session: CallSession, pcm_bytes: bytes):
    if session.processing:
        return
    session.processing = True
    try:
        wav_bytes = pcm_to_wav_bytes(pcm_bytes)
        print(f"[ASR] Sending {len(wav_bytes)} WAV bytes...")
        transcript_chunk = await transcribe_eigen_asr(wav_bytes)

        if not transcript_chunk or len(transcript_chunk.strip()) < 2:
            print("[ASR] Empty transcript, skipping.")
            return

        print(f"[ASR] Got: {transcript_chunk!r}")
        session.full_transcript = (session.full_transcript + " " + transcript_chunk).strip()

        # Send transcript immediately
        await ws.send_text(json.dumps({
            "type": "transcript_update",
            "data": transcript_chunk
        }))

        session.history.append({"role": "user", "content": transcript_chunk})

        # Single LLM call - no duplicate
        print("[LLM] Generating dispatcher response...")
        dispatch_data = await run_dispatch_llm(session.full_transcript, {}, session.history)

        # Send dispatch update
        await ws.send_text(json.dumps({"type": "dispatch_update", "data": dispatch_data}))

        response_text = dispatch_data.get("dispatcher_response_text", "")
        if not response_text:
            return

        session.history.append({"role": "assistant", "content": response_text})

        # TTS - generate voice response
        print(f"[TTS] Synthesizing: {response_text!r}")
        voice_bytes = await synthesize_dispatcher_voice(response_text)
        if voice_bytes:
            b64 = base64.b64encode(voice_bytes).decode("utf-8")
            await ws.send_text(json.dumps({"type": "voice_response", "data": b64}))

    except Exception as e:
        traceback.print_exc()
        try:
            await ws.send_text(json.dumps({"type": "error", "error": str(e)}))
        except Exception:
            pass
    finally:
        session.processing = False




async def process_demo_file(ws, file_path: str):
    try:
        print(f"[Demo] Processing {file_path}")
        with open(file_path, "rb") as f:
            wav_bytes = f.read()

        await ws.send_text(json.dumps({"type": "status", "data": "Processing demo call..."}))

        transcript = await transcribe_eigen_asr(wav_bytes)
        if not transcript:
            transcript = "(could not transcribe demo audio)"

        await ws.send_text(json.dumps({"type": "transcript_update", "data": transcript}))

        dispatch_data = await run_dispatch_llm(transcript, {}, [])
        await ws.send_text(json.dumps({"type": "dispatch_update", "data": dispatch_data}))

        response_text = dispatch_data.get("dispatcher_response_text", "")
        if response_text:
            voice_bytes = await synthesize_dispatcher_voice(response_text)
            if voice_bytes:
                b64 = base64.b64encode(voice_bytes).decode("utf-8")
                await ws.send_text(json.dumps({"type": "voice_response", "data": b64}))

        print("[Demo] Done.")
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
                root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                filepath = os.path.join(root, "demo_calls", filename)
                if os.path.exists(filepath):
                    session = CallSession()
                    asyncio.create_task(process_demo_file(ws, filepath))
                else:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "error": f"Demo file not found: {filename}"
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
