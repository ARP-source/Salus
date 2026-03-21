import { useState } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudioCapture } from './hooks/useAudioCapture';
import type { DispatchResponse } from './types/dispatch';
import './index.css';

function App() {
  const { isConnected, dispatchData, transcriptData, sendMessage } = useWebSocket('ws://localhost:8000/ws');
  const [showReport, setShowReport] = useState(false);

  const { isRecording, startRecording, stopRecording, audioLevel } = useAudioCapture((base64) => {
    sendMessage({ type: 'audio', data: base64 });
  });

  const levelPercent = Math.min(100, Math.max(0, (audioLevel / 255) * 100));

  const getSeverityClass = (sev: string) => {
    switch (sev) {
      case 'CRITICAL': return 'severity-critical';
      case 'SERIOUS': return 'severity-serious';
      case 'MODERATE': return 'severity-moderate';
      default: return 'severity-unknown';
    }
  };

  return (
    <div className="app-container">
      {/* Header */}
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
            <span className="status-text">
              {isConnected ? 'System Online' : 'Connecting...'}
            </span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="main-grid">
        {/* Left Column: Intake & Transcript */}
        <section className="left-column">
          <div className="panel intake-panel">
            <div className="intake-header">
              <span className="label-small">Live Call Intake</span>
              {isRecording && <span className="tag tag-live">LIVE</span>}
            </div>

            <div>
              {!isRecording ? (
                <button
                  onClick={startRecording}
                  disabled={!isConnected}
                  className="btn btn-connect"
                >
                  Connect Call
                </button>
              ) : (
                <button
                  onClick={stopRecording}
                  className="btn btn-end"
                >
                  End Call
                </button>
              )}
            </div>

            <div className="audio-level-container">
              <span className="audio-level-label">Input Level</span>
              <div className="audio-level-track">
                <div className="audio-level-fill" style={{ width: `${levelPercent}%` }} />
              </div>
            </div>
          </div>

          {/* Transcript */}
          <div className="transcript-section">
            <div className="label-small transcript-label">Live Context Stream</div>
            <hr className="transcript-divider" />
            <div className="panel transcript-body">
              {transcriptData || <span className="transcript-placeholder">Awaiting audio input...</span>}
            </div>
          </div>
        </section>

        {/* Right Column: Dispatch Intelligence */}
        <section className="right-column">
          <div className="section-header">
            <div className="section-header-left">
              <h2 className="section-title">Operations Dashboard</h2>
              <span className="section-powered">Powered by Eigen AI</span>
            </div>
            <button
              className="btn btn-secondary"
              onClick={() => setShowReport(true)}
              disabled={!dispatchData}
            >
              Generate Report
            </button>
          </div>

          {/* Dispatch Data */}
          <div className="dispatch-content">
            {!dispatchData ? (
              <div className="panel dispatch-empty">
                <div className="dispatch-empty-icon">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="square" strokeLinejoin="miter">
                    <path d="M12 2L2 22h20L12 2z" />
                    <path d="M12 16v2" />
                    <path d="M12 8v6" />
                  </svg>
                </div>
                <span className="dispatch-empty-text">Waiting for extraction</span>
              </div>
            ) : (
              <DispatchDetails data={dispatchData} getSeverityClass={getSeverityClass} />
            )}
          </div>

          {/* Simulator */}
          <div className="card simulator-panel">
            <div className="simulator-header">
              <span className="label-small">Simulation Scenarios</span>
              <span className="tag tag-hackathon">HACKATHON MODE</span>
            </div>
            <button className="btn-sim">&#9654; EN - Cardiac Arrest</button>
            <button className="btn-sim">&#9654; ES - Structure Fire</button>
            <button className="btn-sim">&#9654; HI - Road Collision</button>
          </div>
        </section>
      </main>

      {/* Report Modal */}
      {showReport && (
        <div className="modal-overlay">
          <div className="panel modal-content">
            <div className="modal-header">
              <h2 className="modal-title">Official Incident Report</h2>
              <button onClick={() => setShowReport(false)} className="modal-close">X</button>
            </div>
            <div className="modal-body">
              {JSON.stringify(dispatchData, null, 2)}
            </div>
            <div className="modal-footer">
              <button onClick={() => setShowReport(false)} className="btn">Close Report</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* Inline sub-component for dispatch details */
function DispatchDetails({ data, getSeverityClass }: { data: DispatchResponse; getSeverityClass: (s: string) => string }) {
  return (
    <div className="dispatch-grid">
      <div className="dispatch-top-row">
        <div className="card dispatch-type-card">
          <div className="label-small" style={{ marginBottom: 4 }}>Emergency Type</div>
          <div className="dispatch-type-value">{data.emergency_type}</div>
        </div>
        <div className="card dispatch-severity-card">
          <div className="label-small" style={{ marginBottom: 8 }}>Severity</div>
          <div className={`severity-badge ${getSeverityClass(data.severity)}`}>
            {data.severity}
          </div>
        </div>
      </div>

      <div className="card location-card">
        <div className="label-small" style={{ marginBottom: 8 }}>Location Intelligence</div>
        <div className="location-details">
          <div>
            <span className="location-sub-label">Extracted:</span>
            <div className="location-value">{data.location_extracted || 'UNKNOWN'}</div>
          </div>
          <div>
            <span className="location-sub-label">Mentioned:</span>
            <div className="location-quote">"{data.location_mentioned || 'No exact quote'}"</div>
          </div>
        </div>
      </div>

      <div className="card caller-state-card">
        <div className="label-small" style={{ marginBottom: 8 }}>Caller State</div>
        <div className="caller-state-row">
          <span className="tag">{data.caller_state}</span>
          <span className="tag tag-language">{data.language_detected}</span>
        </div>
      </div>

      <div className="card details-card">
        <div className="label-small" style={{ marginBottom: 8 }}>Key Actions & Details</div>
        <ul className="details-list">
          {data.key_details.map((detail, i) => (
            <li key={i}>{detail}</li>
          ))}
        </ul>

        <div className="label-small" style={{ marginTop: 16, marginBottom: 8 }}>Recommended Units</div>
        <div className="units-row">
          {data.suggested_units.map((unit) => (
            <span key={unit} className="tag tag-unit">{unit}</span>
          ))}
        </div>
      </div>

      {data.dispatcher_response_text && (
        <div className="card ai-response-card">
          <div className="ai-response-label">AI Voice Response Triggered</div>
          <div className="ai-response-text">"{data.dispatcher_response_text}"</div>
        </div>
      )}
    </div>
  );
}

export default App;
