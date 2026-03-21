import React from 'react';

export const SimulatorPanel: React.FC = () => {
  return (
    <div className="card p-4 flex flex-col gap-2 border-dashed border-border-subtle bg-background-primary">
      <div className="text-[10px] text-text-secondary uppercase tracking-[0.1em] mb-2 flex items-center justify-between">
        <span>Simulation Scenarios</span>
        <span className="tag border border-status-active text-status-active text-[8px]">HACKATHON MODE</span>
      </div>
      <button className="btn text-xs text-left py-1.5 border-border-subtle hover:border-gold-primary">▶ EN - Cardiac Arrest</button>
      <button className="btn text-xs text-left py-1.5 border-border-subtle hover:border-gold-primary">▶ ES - Structure Fire</button>
      <button className="btn text-xs text-left py-1.5 border-border-subtle hover:border-gold-primary">▶ HI - Road Collision</button>
    </div>
  );
};
