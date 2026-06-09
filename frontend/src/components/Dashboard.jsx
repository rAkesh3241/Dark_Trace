import React from 'react';
import { Link } from 'react-router-dom';
import Terminal from './Terminal';

const riskClass = (score = 0) => {
  if (score >= 90) return 'critical';
  if (score >= 70) return 'high';
  if (score >= 40) return 'medium';
  return 'low';
};

const Dashboard = ({ connected, attacks = [], summary = {}, socket, backendUrl }) => {
  const recent = attacks.slice(-6).reverse();
  const highRiskLive = attacks.filter((attack) => (attack.risk_score || 0) >= 70).length;
  const latest = attacks.at(-1);

  const cards = [
    ['Total attacks', summary.total_attacks || attacks.length || 0],
    ['Unique IPs', summary.unique_ips || 0],
    ['High risk', summary.high_risk || highRiskLive || 0],
    ['Latest source', latest?.ip || summary.latest_ip || 'None'],
  ];

  return (
    <div className="dashboard-page">
      <header className="dashboard-hero">
        <div>
          <span className="eyebrow">Command dashboard</span>
          <h2>Live Honeypot Operations</h2>
          <p>Monitor telemetry, run the local console, and jump into investigation views from one screen.</p>
        </div>
        <div className={`dashboard-health ${connected ? 'online' : 'offline'}`}>
          <span>{connected ? 'Socket connected' : 'Socket disconnected'}</span>
          <strong>{connected ? 'Online' : 'Offline'}</strong>
        </div>
      </header>

      <section className="dashboard-stats" aria-label="Dashboard metrics">
        {cards.map(([label, value]) => (
          <article className={label === 'Latest source' ? 'compact-value' : ''} key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </section>

      <section className="dashboard-command-grid">
        <div className="dashboard-terminal">
          <Terminal socket={socket} backendUrl={backendUrl} />
        </div>

        <aside className="dashboard-side">
          <div className="dashboard-card">
            <div className="section-heading">
              <h3>Live Attack Feed</h3>
              <span>{attacks.length} events</span>
            </div>

            <div className="feed-list">
              {recent.map((attack, index) => (
                <article className={`feed-item ${riskClass(attack.risk_score)}`} key={`${attack.ip}-${index}`}>
                  <div>
                    <strong>{attack.ip || 'Unknown IP'}</strong>
                    <span>{attack.eventid || 'session activity'}</span>
                  </div>
                  <p>{attack.command || attack.username || 'Captured interaction'}</p>
                  <b>{attack.risk_score ?? 0}</b>
                </article>
              ))}

              {recent.length === 0 && (
                <div className="empty-panel compact">
                  <strong>No live events yet</strong>
                  <span>Incoming honeypot activity will appear here.</span>
                </div>
              )}
            </div>
          </div>

          <div className="dashboard-card">
            <div className="section-heading">
              <h3>Investigation Shortcuts</h3>
              <span>Drill down</span>
            </div>
            <div className="shortcut-grid">
              <Link to="/logs">Logs</Link>
              <Link to="/analytics">Analytics</Link>
              <Link to="/map">Live Map</Link>
            </div>
          </div>
        </aside>
      </section>
    </div>
  );
};

export default Dashboard;
