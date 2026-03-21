import React from 'react';
import { DispatchResponse } from '../types/dispatch';

interface DispatchPanelProps {
  data: DispatchResponse | null;
}

export const DispatchPanel: React.FC<DispatchPanelProps> = ({ data }) => {
  if (!data) {
    return (
      <div className="panel p-6 flex flex-col items-center justify-center text-text-muted h-full border-dashed">
        <div className="text-gold-dim mb-4">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="square" strokeLinejoin="miter">
            <path d="M12 2L2 22h20L12 2z"/>
            <path d="M12 16v2"/>
            <path d="M12 8v6"/>
          </svg>
        </div>
        <span className="tracking-[0.1em] uppercase text-xs">Waiting for extraction</span>
      </div>
    );
  }

  const getSeverityColor = (sev: string) => {
    switch(sev) {
      case 'CRITICAL': return 'bg-status-critical border border-transparent';
      case 'SERIOUS': return 'bg-status-serious border border-transparent';
      case 'MODERATE': return 'bg-status-moderate border border-transparent';
      default: return 'bg-background-elevated border border-gold-dim';
    }
  };

  return (
    <div className="flex flex-col gap-4 h-full">
      <div className="grid grid-cols-2 gap-4">
        <div className="card p-4 border-l-2 border-l-gold-primary">
          <div className="text-[10px] text-text-secondary uppercase tracking-[0.1em] mb-1">Emergency Type</div>
          <div className="font-mono text-xl text-gold-bright">{data.emergency_type}</div>
        </div>
        <div className="card p-4 flex flex-col justify-center">
          <div className="text-[10px] text-text-secondary uppercase tracking-[0.1em] mb-2">Severity</div>
          <div className={`px-2 py-1 flex justify-center items-center text-xs font-sans tracking-widest uppercase transition-colors rounded-none text-text-primary ${getSeverityColor(data.severity)}`}>
            {data.severity}
          </div>
        </div>
      </div>

      <div className="card p-4">
        <div className="text-[10px] text-text-secondary uppercase tracking-[0.1em] mb-2">Location Intelligence</div>
        <div className="grid grid-cols-1 gap-2 border-l border-gold-dim pl-3">
          <div>
            <span className="text-[10px] text-text-muted uppercase">Extracted:</span>
            <div className="font-mono text-sm text-text-primary">{data.location_extracted || "UNKNOWN"}</div>
          </div>
          <div>
            <span className="text-[10px] text-text-muted uppercase">Mentioned:</span>
            <div className="font-mono text-xs text-gold-dim italic">"{data.location_mentioned || "No exact quote"}"</div>
          </div>
        </div>
      </div>

      <div className="card p-4">
        <div className="text-[10px] text-text-secondary uppercase tracking-[0.1em] mb-2">Caller State</div>
        <div className="flex items-center gap-2">
          <div className="tag">{data.caller_state}</div>
          <div className="tag ml-auto text-gold-primary border-gold-primary">
            {data.language_detected}
          </div>
        </div>
      </div>

      <div className="card p-4 flex-1">
        <div className="text-[10px] text-text-secondary uppercase tracking-[0.1em] mb-2">Key Actions & Details</div>
        <ul className="list-none m-0 p-0 mb-4 space-y-1">
          {data.key_details.map((detail, i) => (
            <li key={i} className="text-xs border-b border-border-subtle pb-1.5 pt-1.5 text-text-primary before:content-['>'] before:text-gold-dim before:mr-2">
              {detail}
            </li>
          ))}
        </ul>

        <div className="text-[10px] text-text-secondary uppercase tracking-[0.1em] mt-4 mb-2">Recommended Units</div>
        <div className="flex flex-wrap gap-2">
          {data.suggested_units.map((unit) => (
            <div key={unit} className="tag bg-status-active border-transparent text-text-primary font-mono text-[10px]">
              {unit}
            </div>
          ))}
        </div>
      </div>
      
      {data.dispatcher_response_text && (
        <div className="card p-4 border-l border-border-subtle bg-background-primary opacity-80 backdrop-saturate-50">
          <div className="text-[10px] text-gold-dim uppercase tracking-widest mb-1">AI Voice Response Triggered</div>
          <div className="text-xs font-mono text-gold-bright italic">"{data.dispatcher_response_text}"</div>
        </div>
      )}
    </div>
  );
};
