/**
 * Data logging controls for recording and exporting data.
 */

import { useDataLogger } from '../contexts/DataLoggerContext';

export function DataLogger() {
  const {
    isLogging,
    entryCount,
    startLogging,
    stopLogging,
    downloadLog,
    clearLog,
  } = useDataLogger();

  return (
    <div className="data-logger">
      <h3>Data Logger</h3>

      <div className="logger-status">
        <span className={`logger-indicator ${isLogging ? 'recording' : ''}`} />
        <span className="logger-text">
          {isLogging ? 'Recording' : 'Stopped'}
        </span>
        {entryCount > 0 && (
          <span className="entry-count">{entryCount} entries</span>
        )}
      </div>

      <div className="logger-controls">
        {!isLogging ? (
          <button className="btn btn-primary" onClick={startLogging}>
            Start Recording
          </button>
        ) : (
          <button className="btn btn-danger" onClick={stopLogging}>
            Stop Recording
          </button>
        )}

        <button
          className="btn btn-secondary"
          onClick={downloadLog}
          disabled={entryCount === 0}
        >
          Download CSV
        </button>

        <button
          className="btn btn-secondary"
          onClick={clearLog}
          disabled={entryCount === 0 || isLogging}
        >
          Clear
        </button>
      </div>

      <p className="logger-info">
        Records temperature, state, and relay data to a CSV file.
      </p>
    </div>
  );
}
