import React from 'react';
import { Link } from 'react-router-dom';

const metricLabel = (value) => value ?? 0;

const LandingPage = ({ summary = {}, attacks = [], connected }) => {
  const latestAttack = attacks.at(-1);
  const posture =
    (summary.high_risk || 0) > 5 ? 'critical' : attacks.length > 0 ? 'elevated' : 'stable';

  return (
    <div className="landing-page honey-landing">
      <div className="honey-visual" aria-hidden="true">
        <div className="hero-grid" />
        <div className="trace trace-one" />
        <div className="trace trace-two" />
        <div className="node node-a" />
        <div className="node node-b" />
        <div className="node node-c" />
      </div>

      <section className="landing-hero">
        <div className="hero-copy">
          <span className={`hero-badge ${connected ? '' : 'disconnected'}`}>
            <i className="badge-dot" />
            {connected ? 'Live honeypot online' : 'Telemetry offline'}
          </span>

          <h2>DarkTrace</h2>
          <p>
            A focused command center for tracking attacker behavior, inspecting captured sessions,
            and turning raw honeypot activity into useful security signals.
          </p>

          <div className="hero-actions">
            <Link className="primary-action" to="/dashboard">Open Dashboard</Link>
            <Link className="secondary-action" to="/analytics">View Analytics</Link>
          </div>
        </div>

        <aside className="hero-console">
          <div className="console-header">
            <span>Threat Posture</span>
            <strong className={`posture ${posture}`}>{posture}</strong>
          </div>
          <div className="console-radar">
            <span />
            <span />
            <span />
            <strong>{metricLabel(summary.total_attacks)}</strong>
            <small>captured events</small>
          </div>
          <div className="console-lines">
            <p>
              <span>Latest IP</span>
              <strong>{latestAttack?.ip || summary.latest_ip || 'Waiting'}</strong>
            </p>
            <p>
              <span>Last command</span>
              <strong>{latestAttack?.command || latestAttack?.eventid || 'No activity yet'}</strong>
            </p>
          </div>
        </aside>
      </section>

      <section className="landing-metrics" aria-label="Honeypot metrics">
        <article>
          <span>Total attacks</span>
          <strong>{metricLabel(summary.total_attacks)}</strong>
        </article>
        <article>
          <span>Unique IPs</span>
          <strong>{metricLabel(summary.unique_ips)}</strong>
        </article>
        <article>
          <span>High risk</span>
          <strong>{metricLabel(summary.high_risk)}</strong>
        </article>
        <article>
          <span>Connection</span>
          <strong>{connected ? 'Online' : 'Offline'}</strong>
        </article>
      </section>

      <section className="landing-preview">
        <div>
          <span className="eyebrow">Operational flow</span>
          <h3>From capture to triage in one workspace</h3>
        </div>

        <div className="workflow-list">
          <Link to="/terminal">
            <span>01</span>
            <strong>Operate the lab terminal</strong>
            <small>Start services, run checks, and interact with the local project console.</small>
          </Link>
          <Link to="/logs">
            <span>02</span>
            <strong>Review captured events</strong>
            <small>Search IPs, credentials, commands, sessions, and risk scores.</small>
          </Link>
          <Link to="/map">
            <span>03</span>
            <strong>Trace attacker origins</strong>
            <small>Watch geolocated attack sources as activity lands.</small>
          </Link>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;
