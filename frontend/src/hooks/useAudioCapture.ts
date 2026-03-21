import { useState, useRef, useCallback } from 'react';

export function useAudioCapture(onAudioData: (base64: string) => void) {
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const [audioLevel, setAudioLevel] = useState(0);

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioContext = new AudioContext();
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      const updateLevel = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
          analyser.getByteFrequencyData(dataArray);
          const sum = dataArray.reduce((acc, val) => acc + val, 0);
          setAudioLevel(sum / dataArray.length);
          requestAnimationFrame(updateLevel);
        }
      };
      
      const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = async (e) => {
        if (e.data.size > 0) {
          const buffer = await e.data.arrayBuffer();
          // Convert array buffer to base64
          const uint8Args = new Uint8Array(buffer);
          let binary = '';
          for (let i = 0; i < uint8Args.byteLength; i++) {
              binary += String.fromCharCode(uint8Args[i]);
          }
          onAudioData(btoa(binary));
        }
      };

      mediaRecorder.start(250); // Timeslice 250ms chunks
      setIsRecording(true);
      requestAnimationFrame(updateLevel);
    } catch (err) {
      console.error("Error accessing microphone", err);
    }
  }, [onAudioData]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
    setIsRecording(false);
    setAudioLevel(0);
  }, []);

  return { isRecording, startRecording, stopRecording, audioLevel };
}
