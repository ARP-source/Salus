import { useState, useRef, useCallback, useEffect } from 'react';

interface AudioCaptureCallbacks {
  onChunk: (base64pcm: string) => void;
  onUtteranceEnd: () => void;
}

// ── VAD config ────────────────────────────────────────────────────────────────
const SAMPLE_RATE       = 16000;
const SILENCE_RMS       = 0.008;   // balanced threshold
const SILENCE_MS        = 700;     // 700ms silence = utterance end (fast response)
const MIN_SPEECH_MS     = 150;     // capture short utterances
const FRAME_SIZE        = 2048;    // samples per processing frame

// ── int16 PCM helpers ─────────────────────────────────────────────────────────
function float32ToInt16Base64(float32: Float32Array): string {
  const int16 = new Int16Array(float32.length);
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  const bytes = new Uint8Array(int16.buffer);
  let binary = '';
  // Process in chunks to avoid stack overflow on large arrays
  const chunkSize = 8192;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

function rms(buf: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
  return Math.sqrt(sum / buf.length);
}

export function useAudioCapture(callbacks: AudioCaptureCallbacks) {
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [isSpeaking, setIsSpeaking] = useState(false);

  // Refs so callbacks in onaudioprocess always see latest values
  const onChunkRef       = useRef(callbacks.onChunk);
  const onUtteranceRef   = useRef(callbacks.onUtteranceEnd);
  useEffect(() => { onChunkRef.current = callbacks.onChunk; }, [callbacks.onChunk]);
  useEffect(() => { onUtteranceRef.current = callbacks.onUtteranceEnd; }, [callbacks.onUtteranceEnd]);

  const ctxRef           = useRef<AudioContext | null>(null);
  const processorRef     = useRef<ScriptProcessorNode | null>(null);
  const sourceRef        = useRef<MediaStreamAudioSourceNode | null>(null);
  const streamRef        = useRef<MediaStream | null>(null);

  // VAD state (mutable, not reactive — lives in the audio thread callback)
  const vadRef = useRef({
    speaking: false,
    speechStart: 0,
    silenceTimer: null as ReturnType<typeof setTimeout> | null,
  });

  const stopRecording = useCallback(() => {
    const vad = vadRef.current;
    if (vad.silenceTimer) { clearTimeout(vad.silenceTimer); vad.silenceTimer = null; }
    vad.speaking = false;

    processorRef.current?.disconnect();
    sourceRef.current?.disconnect();
    ctxRef.current?.close().catch(() => {});
    streamRef.current?.getTracks().forEach(t => t.stop());

    processorRef.current = null;
    sourceRef.current    = null;
    ctxRef.current       = null;
    streamRef.current    = null;

    setIsRecording(false);
    setAudioLevel(0);
    setIsSpeaking(false);
  }, []);

  const startRecording = useCallback(async () => {
    if (isRecording) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          // Request 16kHz — browser may ignore but worth trying
          // @ts-expect-error non-standard
          sampleRate: SAMPLE_RATE,
        }
      });
      streamRef.current = stream;

      // Create context at 16kHz for Eigen ASR compatibility
      const ctx = new AudioContext({ sampleRate: SAMPLE_RATE });
      ctxRef.current = ctx;

      const source = ctx.createMediaStreamSource(stream);
      sourceRef.current = source;

      // ScriptProcessorNode — deprecated but universally supported
      // AudioWorklet would be better but requires extra infra
      const processor = ctx.createScriptProcessor(FRAME_SIZE, 1, 1);
      processorRef.current = processor;

      const vad = vadRef.current;
      vad.speaking   = false;
      vad.speechStart = 0;
      if (vad.silenceTimer) clearTimeout(vad.silenceTimer);
      vad.silenceTimer = null;

      processor.onaudioprocess = (ev) => {
        const buf = ev.inputBuffer.getChannelData(0);
        const level = rms(buf);

        // Update UI level meter (0–255)
        setAudioLevel(Math.min(255, Math.round(level * 2000)));

        const silent = level < SILENCE_RMS;
        const now = Date.now();

        if (!silent) {
          // ── Speech frame ──────────────────────────────────────────────────
          if (!vad.speaking) {
            vad.speaking   = true;
            vad.speechStart = now;
            setIsSpeaking(true);
          }
          // Cancel any pending silence timer
          if (vad.silenceTimer) {
            clearTimeout(vad.silenceTimer);
            vad.silenceTimer = null;
          }
        }
        
        // Always send audio while speaking (including quiet parts)
        if (vad.speaking) {
          onChunkRef.current(float32ToInt16Base64(buf));
        }

        if (silent && vad.speaking && !vad.silenceTimer) {
          // ── Just went silent — start countdown ────────────────────────────
          const speechDur = now - vad.speechStart;
          vad.silenceTimer = setTimeout(() => {
            vad.speaking     = false;
            vad.silenceTimer = null;
            setIsSpeaking(false);

            if (speechDur >= MIN_SPEECH_MS) {
              console.log(`[VAD] Utterance end (speech: ${speechDur}ms)`);
              onUtteranceRef.current();
            } else {
              console.log(`[VAD] Blip ignored (${speechDur}ms < ${MIN_SPEECH_MS}ms)`);
            }
          }, SILENCE_MS);
        }
      };

      source.connect(processor);
      // Must connect to destination for onaudioprocess to fire in Chrome
      processor.connect(ctx.destination);

      setIsRecording(true);
      console.log(`[AudioCapture] Started — context SR: ${ctx.sampleRate}Hz`);

    } catch (err) {
      console.error('[AudioCapture] Mic error:', err);
      alert(`Microphone error: ${(err as Error).message}`);
    }
  }, [isRecording]);

  return { isRecording, startRecording, stopRecording, audioLevel, isSpeaking };
}
