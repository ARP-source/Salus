import React from 'react';

interface AudioLevelMeterProps {
  level: number;
}

export const AudioLevelMeter: React.FC<AudioLevelMeterProps> = ({ level }) => {
  const percentage = Math.min(100, Math.max(0, (level / 255) * 100));
  
  return (
    <div className="flex flex-col gap-1 w-full max-w-[200px]">
      <div className="text-[10px] text-text-secondary tracking-widest uppercase">Input Level</div>
      <div className="w-full h-1.5 bg-background-elevated border border-gold-dim rounded-none overflow-hidden">
        <div 
          className="h-full bg-gold-primary transition-all duration-75"
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
};
