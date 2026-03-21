# Salus — Government Emergency Dispatch Intelligence System

Salus is an AI system that fully replaces a human emergency dispatch officer, providing panic-robust speech understanding, real-time voice conversation, language barrier elimination, and dispatch intelligence extraction.

## Features
- **Panic/Noise Robustness**: Understands speech through distress using Boson's audio semantics models.
- **Language Barrier Elimination**: Real-time auto-translation and communication in the caller's native language.
- **Live Operator Dashboard**: WebSockets-driven React frontend displaying extracted intelligence in real-time.
- **Emergency Intelligence Extraction**: Extracts type, severity, location, caller state, and generates dispatch actions.
- **Simulation Mode**: Includes hackathon demos (Cardic Arrest/Structure Fire/Road Collision) synthesized via Eigen AI.

## Built With
- **Backend Orchestrator**: FastAPI, WebSockets
- **Frontend Dashboard**: React, Vite, Tailwind CSS (Midnight Gold Palette)
- **Audio Intelligence**: Boson AI (`higgs-audio-understanding-v3.5-Hackathon`)
- **Fast ASR & TTS**: Eigen Cloud (`higgs_asr_3`, `higgs2p5`)
- **Dispatch Logic Brain**: Eigen Cloud (`gpt-oss-120b`)

## Setup Instructions

1. **Environment Config**
   Copy `.env.example` to `.env` and configure your API keys:
   ```env
   BOSONAI_API_KEY=your_key
   EIGEN_API_KEY=your_key
   PORT=8000
   ```
   *Never log or hardcode these keys.*

2. **Run via Docker Compose**
   ```sh
   docker-compose up --build
   ```
   - Dashboard: `http://localhost:5173`
   - Backend WS: `ws://localhost:8000/ws`

3. **Run Manually**
   - **Backend**:
     ```sh
     cd backend
     pip install -r requirements.txt
     uvicorn main:app --host 0.0.0.0 --port 8000
     ```
   - **Frontend**:
     ```sh
     cd frontend
     npm install
     npm run dev
     ```

## Generating Demo Calls
To reproduce the hackathon simulation calls, ensure `EIGEN_API_KEY` is set and run:
```sh
python demo_calls/generate_demos.py
```
