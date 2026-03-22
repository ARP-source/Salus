import { useRef, useState } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioCapture } from './hooks/useAudioCapture';
import type { DispatchResponse } from './types/dispatch';
import './index.css';

const WS_URL = 'ws://localhost:8000/ws';

export default function App() {
  const { isConnected, dispatchData, transcriptData, statusMsg, send, resetSession } =
    useWebSocket(WS_URL);
  const [showReport, setShowReport] = useState(false);

  // Stable callback refs — avoids re-creating useAudioCapture on every render
  const sendRef = useRef(send);
  sendRef.current = send;

  const { isRecording, startRecording, stopRecording, audioLevel, isSpeaking } =
    useAudioCapture({
      onChunk: (b64) => sendRef.current({ type: 'audio_chunk', data: b64 }),
      onUtteranceEnd: () => sendRef.current({ type: 'utterance_end' }),
    });

  const levelPct = Math.min(100, Math.max(0, (audioLevel / 255) * 100));

  const handleEndCall = () => {
    stopRecording();
    sendRef.current({ type: 'stop' });
  };

  const handleSimulate = (file: string) => {
    resetSession();
    send({ type: 'simulate', data: file });
  };

  const sev = (s: string) =>
    ({ CRITICAL: 'severity-critical', SERIOUS: 'severity-serious', MODERATE: 'severity-moderate' }[s] ?? 'severity-unknown');

  return (
    <div className="app-container">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="header">
        <div className="header-left">
          <div className="header-logo" />
          <h1 className="header-title">SALUS</h1>
          <div className="header-divider" />
          <span className="header-subtitle">Emergency Dispatch Intelligence</span>
        </div>
        <div className="header-right">
          <div className="status-indicator">
            <div className={`status-dot ${isConnected ? 'online' : 'offline'}`} />
            <span className="status-text">{isConnected ? 'System Online' : 'Reconnecting…'}</span>
          </div>
        </div>
      </header>

      {/* ── Main ───────────────────────────────────────────────────────────── */}
      <main className="main-grid">

        {/* Left column */}
        <section className="left-column">

          {/* Intake panel */}
          <div className="panel intake-panel">
            <div className="intake-header">
              <span className="label-small">Live Call Intake</span>
              <div style={{ display: 'flex', gap: 8 }}>
                {isRecording && isSpeaking  && <span className="tag tag-live">● SPEAKING</span>}
                {isRecording && !isSpeaking && <span className="tag" style={{ color: 'var(--status-active)', borderColor: 'var(--status-active)' }}>○ LISTENING</span>}
              </div>
            </div>

            {/* Call controls */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {!isRecording ? (
                <button onClick={startRecording} disabled={!isConnected} className="btn btn-connect">
                  Connect Call
                </button>
              ) : (
                <button onClick={handleEndCall} className="btn btn-end">
                  End Call
                </button>
              )}
              {!isRecording && (dispatchData || transcriptData) && (
                <button onClick={resetSession} className="btn btn-secondary" style={{ width: '100%' }}>
                  Clear / New Call
                </button>
              )}
            </div>

            {/* Level meter */}
            <div className="audio-level-container">
              <span className="audio-level-label">
                {isRecording ? (isSpeaking ? '● Speech detected' : '○ Monitoring…') : 'Input Level'}
              </span>
              <div className="audio-level-track">
                <div
                  className="audio-level-fill"
                  style={{
                    width: `${levelPct}%`,
                    background: isSpeaking ? 'var(--gold-primary)' : 'var(--gold-dim)',
                    transition: 'width 60ms linear, background 200ms ease',
                  }}
                />
              </div>
            </div>

            {statusMsg && (
              <div style={{ fontSize: 10, color: 'var(--text-secondary)', letterSpacing: '0.1em' }}>
                {statusMsg}
              </div>
            )}
          </div>

          {/* Transcript */}
          <div className="transcript-section">
            <div className="label-small transcript-label">Live Context Stream</div>
            <hr className="transcript-divider" />
            <div className="panel transcript-body">
              {transcriptData
                ? transcriptData
                : <span className="transcript-placeholder">
                    {isRecording ? 'Speak now — listening…' : 'Awaiting audio input…'}
                  </span>
              }
            </div>
          </div>
        </section>

        {/* Right column */}
        <section className="right-column">
          <div className="section-header">
            <div className="section-header-left">
              <h2 className="section-title">Operations Dashboard</h2>
              <span className="section-powered">Powered by Eigen AI</span>
            </div>
            <button className="btn btn-secondary" onClick={() => setShowReport(true)} disabled={!dispatchData}>
              Generate Report
            </button>
          </div>

          {/* Dispatch panel */}
          <div className="dispatch-content">
            {!dispatchData ? (
              <div className="panel dispatch-empty">
                <div className="dispatch-empty-icon">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="square">
                    <path d="M12 2L2 22h20L12 2z"/><path d="M12 16v2"/><path d="M12 8v6"/>
                  </svg>
                </div>
                <span className="dispatch-empty-text">
                  {isRecording ? 'Processing call…' : 'Waiting for extraction'}
                </span>
              </div>
            ) : (
              <DispatchDetails data={dispatchData} sev={sev} />
            )}
          </div>

          {/* Simulator */}
          <div className="card simulator-panel">
            <div className="simulator-header">
              <span className="label-small">Simulation Scenarios</span>
              <span className="tag tag-hackathon">HACKATHON MODE</span>
            </div>
            <button className="btn-sim" onClick={() => handleSimulate('en_cardiac_arrest.wav')}>▶ EN — Cardiac Arrest</button>
            <button className="btn-sim" onClick={() => handleSimulate('es_structure_fire.wav')}>▶ ES — Structure Fire</button>
            <button className="btn-sim" onClick={() => handleSimulate('hi_road_collision.wav')}>▶ HI — Road Collision</button>
          </div>
        </section>
      </main>

      {/* Report modal */}
      {showReport && (
        <div className="modal-overlay">
          <div className="panel modal-content">
            <div className="modal-header">
              <h2 className="modal-title">Official Incident Report</h2>
              <button onClick={() => setShowReport(false)} className="modal-close">✕</button>
            </div>
            <div className="modal-body">{JSON.stringify(dispatchData, null, 2)}</div>
            <div className="modal-footer">
              <button onClick={() => setShowReport(false)} className="btn">Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Dispatch details sub-component ────────────────────────────────────────────
function DispatchDetails({ data, sev }: { data: DispatchResponse; sev: (s: string) => string }) {
  return (
    <div className="dispatch-grid">

      <div className="dispatch-top-row">
        <div className="card dispatch-type-card">
          <div className="label-small" style={{ marginBottom: 4 }}>Emergency Type</div>
          <div className="dispatch-type-value">{data.emergency_type}</div>
        </div>
        <div className="card dispatch-severity-card">
          <div className="label-small" style={{ marginBottom: 8 }}>Severity</div>
          <div className={`severity-badge ${sev(data.severity)}`}>{data.severity}</div>
        </div>
      </div>

      <div className="card location-card">
        <div className="label-small" style={{ marginBottom: 8 }}>Location Intelligence</div>
        <div className="location-details">
          <div>
            <span className="location-sub-label">Extracted: </span>
            <div className="location-value">{data.location_extracted || 'UNKNOWN'}</div>
          </div>
          <div>
            <span className="location-sub-label">Mentioned: </span>
            <div className="location-quote">"{data.location_mentioned || 'No exact quote'}"</div>
          </div>
        </div>
      </div>

      <div className="card caller-state-card">
        <div className="label-small" style={{ marginBottom: 8 }}>Caller State</div>
        <div className="caller-state-row">
          <span className="tag">{data.caller_state}</span>
          <span className="tag tag-language">{data.language_detected?.toUpperCase()}</span>
          {data.needs_translation && (
            <span className="tag" style={{ color: 'var(--status-serious)', borderColor: 'var(--status-serious)' }}>
              TRANSLATING
            </span>
          )}
          {data.immediate_action && (
            <span className="tag tag-live">IMMEDIATE</span>
          )}
        </div>
      </div>

      <div className="card details-card">
        <div className="label-small" style={{ marginBottom: 8 }}>Key Actions & Details</div>
        <ul className="details-list">
          {data.key_details.map((d, i) => <li key={i}>{d}</li>)}
        </ul>

        <div className="label-small" style={{ marginTop: 16, marginBottom: 8 }}>Recommended Units</div>
        <div className="units-row">
          {data.suggested_units.map(u => <span key={u} className="tag tag-unit">{u}</span>)}
        </div>

        <div style={{ marginTop: 12, fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>
          CONFIDENCE: {Math.round((data.confidence_score ?? 0) * 100)}%
        </div>
      </div>

      {data.dispatcher_response_text && (
        <div className="card ai-response-card">
          <div className="ai-response-label">AI Dispatcher Response (spoken aloud)</div>
          <div className="ai-response-text">"{data.dispatcher_response_text}"</div>
          {data.needs_translation && data.translation_english && (
            <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-secondary)', fontStyle: 'italic' }}>
              EN: {data.translation_english}
            </div>
          )}
        </div>
      )}

    </div>
  );
}
