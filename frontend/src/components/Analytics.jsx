import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Bar, Line } from 'react-chartjs-2';
import {
  Chart as ChartJS, CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, Title, Tooltip, Legend, Filler,
} from 'chart.js';

ChartJS.register(
  CategoryScale, LinearScale, BarElement,
  LineElement, PointElement, Title, Tooltip, Legend, Filler
);

const CHART_OPTS = (title) => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { labels: { color: '#a7b4c6' } },
    title: {
      display: true,
      text: title,
      color: '#eef4ff',
      font: { size: 14, weight: '700' },
    },
  },
  scales: {
    x: {
      ticks: { color: '#a7b4c6' },
      grid: { color: 'rgba(126, 149, 185, 0.16)' },
    },
    y: {
      beginAtZero: true,
      ticks: { color: '#a7b4c6', precision: 0 },
      grid: { color: 'rgba(126, 149, 185, 0.16)' },
    },
  },
});

const hasChartData = (data) => data?.datasets?.some((set) => set.data?.some((value) => value > 0));

const EmptyChart = ({ title, detail }) => (
  <div className="analytics-empty-chart">
    <strong>{title}</strong>
    <span>{detail}</span>
  </div>
);

const Analytics = ({ backendUrl = 'http://localhost:5000' }) => {
  const [cmdData, setCmdData] = useState(null);
  const [timelineData, setTimelineData] = useState(null);
  const [clusters, setClusters] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cmdRes, timeRes, clusterRes] = await Promise.all([
        fetch(`${backendUrl}/api/command-stats`).then((response) => response.json()),
        fetch(`${backendUrl}/api/timeline`).then((response) => response.json()),
        fetch(`${backendUrl}/api/clusters`).then((response) => response.json()),
      ]);

      setCmdData({
        labels: cmdRes.labels || [],
        datasets: [{
          label: 'Command Count',
          data: cmdRes.values || [],
          backgroundColor: 'rgba(125, 92, 255, 0.58)',
          borderColor: '#9f8cff',
          borderWidth: 1,
        }],
      });

      setTimelineData({
        labels: timeRes.labels || [],
        datasets: [{
          label: 'Attacks / Hour',
          data: timeRes.values || [],
          fill: true,
          backgroundColor: 'rgba(45, 212, 191, 0.1)',
          borderColor: '#2dd4bf',
          tension: 0.38,
          pointRadius: 3,
          pointBackgroundColor: '#2dd4bf',
        }],
      });

      setClusters(clusterRes.data || []);
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Analytics fetch failed:', err);
    } finally {
      setLoading(false);
    }
  }, [backendUrl]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  const totals = useMemo(() => {
    const commandTotal = cmdData?.datasets?.[0]?.data?.reduce((sum, value) => sum + Number(value || 0), 0) || 0;
    const peakHour = Math.max(0, ...(timelineData?.datasets?.[0]?.data || [0]));
    const highRisk = clusters.filter((cluster) => cluster.risk_score >= 70).length;
    return { commandTotal, peakHour, highRisk };
  }, [cmdData, timelineData, clusters]);

  const clusterColors = ['#2dd4bf', '#f59e0b', '#fb7185'];
  const clusterLabels = ['Low Risk', 'Medium Risk', 'High Risk'];

  return (
    <div className="analytics-page">
      <div className="analytics-header">
        <div>
          <span>Threat intelligence</span>
          <h2>Analytics & Attacker Profiling</h2>
          <p>Command frequency, attack timing, and attacker session clustering in one view.</p>
        </div>
        <button className="refresh-btn" onClick={load} disabled={loading}>
          {loading ? 'Refreshing' : 'Refresh'}
        </button>
      </div>

      <div className="analytics-summary">
        <article>
          <span>Total commands</span>
          <strong>{totals.commandTotal}</strong>
        </article>
        <article>
          <span>Peak hourly attacks</span>
          <strong>{totals.peakHour}</strong>
        </article>
        <article>
          <span>Clustered sessions</span>
          <strong>{clusters.length}</strong>
        </article>
        <article>
          <span>High risk clusters</span>
          <strong>{totals.highRisk}</strong>
        </article>
      </div>

      <div className="analytics-grid">
        <div className="analytics-card tall">
          <div className="chart-frame">
            {hasChartData(cmdData)
              ? <Bar data={cmdData} options={CHART_OPTS('Top Commands by Frequency')} />
              : <EmptyChart title="No command data yet" detail="Run terminal commands or ingest honeypot logs to populate this chart." />}
          </div>
        </div>

        <div className="analytics-card tall">
          <div className="chart-frame">
            {hasChartData(timelineData)
              ? <Line data={timelineData} options={CHART_OPTS('Attacks Over Last 24 Hours')} />
              : <EmptyChart title="No timeline activity yet" detail="New events will form an hourly activity trend here." />}
          </div>
        </div>

        <div className="analytics-card wide">
          <div className="section-heading">
            <h3>Attacker Session Clusters</h3>
            <span>{lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : 'Waiting'}</span>
          </div>

          <div className="analytics-table-wrap">
            <table className="analytics-table">
              <thead>
                <tr>
                  <th>IP</th>
                  <th>Session</th>
                  <th>Commands</th>
                  <th>Count</th>
                  <th>Risk</th>
                  <th>Cluster</th>
                </tr>
              </thead>

              <tbody>
                {clusters.map((cluster, index) => (
                  <tr key={`${cluster.ip || 'ip'}-${index}`}>
                    <td>{cluster.ip}</td>
                    <td>{(cluster.session || '').slice(0, 12)}...</td>
                    <td>{(cluster.commands || []).slice(0, 5).join(', ')}</td>
                    <td>{cluster.count}</td>
                    <td>{cluster.risk_score}</td>
                    <td>
                      <span
                        className="cluster-pill"
                        style={{
                          '--cluster-color': clusterColors[cluster.cluster] || clusterColors[0],
                        }}
                      >
                        {clusterLabels[cluster.cluster] || 'Unclassified'}
                      </span>
                    </td>
                  </tr>
                ))}

                {clusters.length === 0 && (
                  <tr>
                    <td colSpan={6}>
                      <div className="table-empty">
                        <strong>No attacker sessions yet</strong>
                        <span>Once logs arrive, grouped attacker behavior will appear here.</span>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Analytics;
