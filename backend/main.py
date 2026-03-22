from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI(title="Salus Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

import base64
import json
import os
import asyncio
import tempfile
import traceback
from transcription import call_boson_transcription
from dispatch_brain import run_dispatch_llm
from voice_response import synthesize_dispatcher_voice
from audio_utils import chunk_audio_file

async def process_audio_file(websocket: WebSocket, file_path: str):
    try:
        # 1. Chunk audio and stream transcript immediately using Eigen fast ASR fallback if needed (Boson takes care of logic)
        print(f"[{file_path}] Processing audio file...")
        chunks, metadata = chunk_audio_file(file_path)
        
        # 2. Boson Transcription / Deep Audio Understanding
        print(f"[{file_path}] Requesting Boson AI transcript...")
        transcript = await call_boson_transcription(chunks)
        await websocket.send_text(json.dumps({"type": "transcript_update", "data": transcript}))
        
        # 3. Eigen Cloud Dispatch Intelligence Extraction
        print(f"[{file_path}] Running Eigen Cloud gpt-oss-120b intelligence...")
        dispatch_data = await run_dispatch_llm(transcript, metadata, [])
        await websocket.send_text(json.dumps({"type": "dispatch_update", "data": dispatch_data}))
        
        # 4. Synthesize AI Dispatcher Voice Response
        if "dispatcher_response_text" in dispatch_data and dispatch_data["dispatcher_response_text"]:
            print(f"[{file_path}] Synthesizing dispatcher voice response...")
            voice_bytes = await synthesize_dispatcher_voice(dispatch_data["dispatcher_response_text"])
            if voice_bytes:
                b64_audio = base64.b64encode(voice_bytes).decode('utf-8')
                await websocket.send_text(json.dumps({"type": "voice_response", "data": b64_audio}))
                
        print(f"[{file_path}] Finished processing.")
    except Exception as e:
        traceback.print_exc()
        await websocket.send_text(json.dumps({"type": "error", "error": str(e)}))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        live_audio_buffer = bytearray()
        
        while True:
            raw_msg = await websocket.receive_text()
            try:
                msg = json.loads(raw_msg)
            except Exception:
                continue
                
            msg_type = msg.get("type")
            
            if msg_type == "simulate":
                filename = msg.get("data")
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                filepath = os.path.join(project_root, "demo_calls", filename)
                if os.path.exists(filepath):
                    # Process asynchronously to not block UI loop
                    asyncio.create_task(process_audio_file(websocket, filepath))
                else:
                    await websocket.send_text(json.dumps({"type": "error", "error": f"Demo file not found: {filepath}"}))
            
            elif msg_type == "audio":
                b64_data = msg.get("data")
                if b64_data:
                    live_audio_buffer.extend(base64.b64decode(b64_data))
                    
            elif msg_type == "stop":
                if live_audio_buffer:
                    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                        tmp.write(live_audio_buffer)
                        tmp_path = tmp.name
                    live_audio_buffer = bytearray()
                    # Trigger processing and delete temporary WebM after
                    async def run_and_cleanup():
                        await process_audio_file(websocket, tmp_path)
                        os.unlink(tmp_path)
                    asyncio.create_task(run_and_cleanup())
                    
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
