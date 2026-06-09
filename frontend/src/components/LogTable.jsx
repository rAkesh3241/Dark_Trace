import React, { useState, useEffect, useCallback } from 'react';

const getRiskClass = (score) => {
  if (score >= 70) return 'danger';
  if (score >= 40) return 'warning';
  return 'safe';
};

const LogTable = ({ backendUrl = "http://localhost:5000" }) => {
  const [logs, setLogs] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${backendUrl}/api/logs?limit=200${
          search ? `&search=${encodeURIComponent(search)}` : ''
        }`
      );

      const data = await res.json();
      setLogs(data);
    } catch (err) {
      console.error('Log fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [backendUrl, search]);

  useEffect(() => {
    loadLogs();

    const interval = setInterval(loadLogs, 5000); // refresh every 5s
    return () => clearInterval(interval);
  }, [loadLogs]);

  return (
    <div>
      {/* Controls */}
      <div
        className="log-controls"
        style={{ display: 'flex', gap: 12, alignItems: 'center' }}
      >
        <input
          className="search-input"
          type="text"
          placeholder="Search IP, command, username…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />

        <span style={{ color: '#8e9bb0', fontSize: '0.82rem' }}>
          {loading ? 'Refreshing…' : `${logs.length} entries`}
        </span>
      </div>

      {/* Table */}
      <table className="log-table">
        <thead>
          <tr>
            <th>Time</th>
            <th>IP</th>
            <th>Location</th>
            <th>Command / Event</th>
            <th>Username</th>
            <th>Risk</th>
          </tr>
        </thead>

        <tbody>
          {logs.map((log, index) => (
            <tr key={log.id || index} className={getRiskClass(log.risk_score)}>
              <td>{new Date(log.timestamp).toLocaleTimeString()}</td>
              <td>{log.ip}</td>
              <td>
                {[log.city, log.country].filter(Boolean).join(', ') || '--'}
              </td>
              <td
                style={{
                  maxWidth: 320,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {log.command || log.eventid || log.message}
              </td>
              <td>{log.username || '--'}</td>
              <td>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: 999,
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    background:
                      log.risk_score >= 70
                        ? 'rgba(255,84,112,0.15)'
                        : log.risk_score >= 40
                        ? 'rgba(255,209,102,0.15)'
                        : 'rgba(34,245,139,0.15)',
                    color:
                      log.risk_score >= 70
                        ? '#ff5470'
                        : log.risk_score >= 40
                        ? '#ffd166'
                        : '#22f58b',
                  }}
                >
                  {log.risk_score}
                </span>
              </td>
            </tr>
          ))}

          {logs.length === 0 && (
            <tr>
              <td
                colSpan={6}
                style={{
                  color: '#8e9bb0',
                  textAlign: 'center',
                  padding: 24,
                }}
              >
                No logs yet
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default LogTable;
