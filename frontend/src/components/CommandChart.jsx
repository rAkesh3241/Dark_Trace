import React from 'react';

// This component is now just the live Recent Attacks list for the dashboard sidebar.
// The bar chart lives in Analytics.jsx.
const RecentAttacks = ({ attacks }) => {
  const riskColor = (score) => {
    if (score >= 90) return '#ff5470';
    if (score >= 70) return '#ffd166';
    if (score >= 40) return '#00d1ff';
    return '#22f58b';
  };

  return (
    <div className="recent-attacks">
      <div className="section-heading">
        <h3>Live Attacks</h3>
        <span>{attacks.length} total</span>
      </div>
      <ul>
        {attacks.slice(-8).reverse().map((a, i) => (
          <li key={i} style={{ borderLeft:`3px solid ${riskColor(a.risk_score)}`, paddingLeft:10, marginBottom:10 }}>
            <span style={{ color:'#00d1ff', fontSize:'0.78rem' }}>
              {a.ip} {a.city ? `· ${a.city}` : ''}
            </span>
            <strong style={{ display:'block', fontFamily:'monospace', fontSize:'0.88rem', marginTop:2 }}>
              {a.command}
            </strong>
            <span style={{ color: riskColor(a.risk_score), fontSize:'0.72rem', fontWeight:700 }}>
              Risk: {a.risk_score}
            </span>
          </li>
        ))}
        {attacks.length === 0 && (
          <li className="empty-state">Waiting for live attack telemetry…</li>
        )}
      </ul>
    </div>
  );
};

export default RecentAttacks;