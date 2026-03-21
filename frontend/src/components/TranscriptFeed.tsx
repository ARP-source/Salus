import React, { useEffect, useRef } from 'react';

interface TranscriptFeedProps {
  transcript: string;
}

export const TranscriptFeed: React.FC<TranscriptFeedProps> = ({ transcript }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [transcript]);

  return (
    <div className="flex flex-col h-full min-h-[300px]">
      <div className="section-label mb-2 text-gold-primary">Live Context Stream</div>
      <div className="divider" />
      <div 
        ref={containerRef}
        className="flex-1 overflow-y-auto mt-2 p-4 panel font-mono text-sm text-text-primary leading-relaxed whitespace-pre-wrap rounded-none"
      >
        {transcript || <span className="text-text-muted">Awaiting audio input...</span>}
      </div>
    </div>
  );
};
