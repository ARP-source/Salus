import { useState, useEffect, useRef, useCallback } from 'react';
import { DispatchResponse, WebsocketMessage } from '../types/dispatch';

export function useWebSocket(url: string) {
  const [isConnected, setIsConnected] = useState(false);
  const [dispatchData, setDispatchData] = useState<DispatchResponse | null>(null);
  const [transcriptData, setTranscriptData] = useState<string>("");
  
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => setIsConnected(true);
    ws.onclose = () => setIsConnected(false);
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'dispatch_update' && msg.data) {
          setDispatchData(msg.data);
        } else if (msg.type === 'transcript_update' && msg.data) {
          setTranscriptData(prev => prev ? prev + " " + msg.data : msg.data);
        } else if (msg.type === 'voice_response' && msg.data) {
            // Play audio
            const audio = new Audio("data:audio/wav;base64," + msg.data);
            audio.play();
        }
      } catch (err) {
        console.error("Failed to parse websocket message", err);
      }
    };

    return () => {
      ws.close();
    };
  }, [url]);

  const sendMessage = useCallback((msg: WebsocketMessage) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { isConnected, dispatchData, transcriptData, sendMessage };
}
