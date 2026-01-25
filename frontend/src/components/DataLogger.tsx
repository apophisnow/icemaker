/**
 * Data logging controls for recording and exporting data.
 */

import { useState } from 'react';
import { useDataLogger } from '../contexts/DataLoggerContext';

export function DataLogger() {
  const [isExpanded, setIsExpanded] = useState(false);
  const {
    isLogging,
    entryCount,
    startLogging,
    stopLogging,
    downloadLog,
    clearLog,
  } = useDataLogger();

  return (
    <div className={`data-logger ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <button
        className="logger-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="logger-title">
          <span className={`logger-indicator ${isLogging ? 'recording' : ''}`} />
          Data Logger
          {entryCount > 0 && (
            <span className="entry-count">{entryCount}</span>
          )}
        </span>
        <span className={`expand-icon ${isExpanded ? 'open' : ''}`}>▼</span>
      </button>

      {isExpanded && (
        <div className="logger-content">
          <div className="logger-status">
            <span className="logger-text">
              {isLogging ? 'Recording...' : 'Stopped'}
            </span>
          </div>

          <div className="logger-controls">
            {!isLogging ? (
              <button className="btn btn-primary" onClick={startLogging}>
                Start
              </button>
            ) : (
              <button className="btn btn-danger" onClick={stopLogging}>
                Stop
              </button>
            )}

            <button
              className="btn btn-secondary"
              onClick={downloadLog}
              disabled={entryCount === 0}
            >
              Download
            </button>

            <button
              className="btn btn-secondary"
              onClick={clearLog}
              disabled={entryCount === 0 || isLogging}
            >
              Clear
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
