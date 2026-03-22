import { useState, useEffect, useRef, useCallback } from 'react';
import type { DispatchResponse } from '../types/dispatch';

export interface WsMessage {
  type: string;
  data?: unknown;
}

export function useWebSocket(url: string) {
  const [isConnected, setIsConnected]     = useState(false);
  const [dispatchData, setDispatchData]   = useState<DispatchResponse | null>(null);
  const [transcriptData, setTranscript]   = useState('');
  const [statusMsg, setStatusMsg]         = useState('');

  const wsRef            = useRef<WebSocket | null>(null);
  const reconnTimerRef   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const audioQueueRef    = useRef<string[]>([]);
  const playingRef       = useRef(false);

  // ── Audio playback queue (FIFO, no overlap) ────────────────────────────────
  const playNext = useCallback(() => {
    if (playingRef.current || audioQueueRef.current.length === 0) return;
    const b64 = audioQueueRef.current.shift()!;
    playingRef.current = true;

    // Detect format: WAV starts with "UklGR" (base64 of "RIFF")
    const mime = b64.startsWith('UklGR') ? 'audio/wav' : 'audio/mpeg';
    const audio = new Audio(`data:${mime};base64,${b64}`);

    audio.onended  = () => { playingRef.current = false; playNext(); };
    audio.onerror  = (e) => {
      console.warn('[Audio] Playback error, trying wav fallback', e);
      // Try WAV if mp3 failed
      const audio2 = new Audio(`data:audio/wav;base64,${b64}`);
      audio2.onended = () => { playingRef.current = false; playNext(); };
      audio2.onerror = () => { playingRef.current = false; playNext(); };
      audio2.play().catch(() => { playingRef.current = false; playNext(); });
    };
    audio.play().catch((e) => {
      console.error('[Audio] Play failed:', e);
      playingRef.current = false;
      playNext();
    });
  }, []);

  // ── WebSocket connect / reconnect ─────────────────────────────────────────
  useEffect(() => {
    let destroyed = false;

    const connect = () => {
      if (destroyed) return;
      console.log('[WS] Connecting to', url);
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WS] Connected');
        setIsConnected(true);
      };

      ws.onclose = () => {
        console.log('[WS] Closed — reconnecting in 2s');
        setIsConnected(false);
        if (!destroyed) reconnTimerRef.current = setTimeout(connect, 2000);
      };

      ws.onerror = (e) => console.error('[WS] Error', e);

      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data as string);
          switch (msg.type) {
            case 'transcript_update':
              setTranscript(prev => (prev ? prev + ' ' : '') + msg.data);
              break;
            case 'dispatch_update':
              setDispatchData(msg.data as DispatchResponse);
              break;
            case 'voice_response':
              audioQueueRef.current.push(msg.data as string);
              playNext();
              break;
            case 'status':
              setStatusMsg(String(msg.data));
              break;
            case 'error':
              console.error('[WS] Backend error:', msg.error);
              setStatusMsg(`Error: ${msg.error}`);
              break;
          }
        } catch (e) {
          console.error('[WS] Parse error', e);
        }
      };
    };

    connect();

    return () => {
      destroyed = true;
      if (reconnTimerRef.current) clearTimeout(reconnTimerRef.current);
      wsRef.current?.close();
    };
  }, [url, playNext]);

  const send = useCallback((msg: WsMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    } else {
      console.warn('[WS] send() called but socket not open');
    }
  }, []);

  const resetSession = useCallback(() => {
    setTranscript('');
    setDispatchData(null);
    setStatusMsg('');
    audioQueueRef.current = [];
  }, []);

  return { isConnected, dispatchData, transcriptData, statusMsg, send, resetSession };
}
