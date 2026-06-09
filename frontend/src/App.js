import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import Terminal from './components/Terminal';
import LogTable from './components/LogTable';
import Analytics from './components/Analytics';
import AttackMap from './components/AttackMap';
import LandingPage from './components/LandingPage';
import LoginPage from './components/LoginPage';
import Dashboard from './components/Dashboard';
import DarkTraceLogo from './components/DarkTraceLogo';
import io from 'socket.io-client';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import './App.css';

const BACKEND = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5001';

const socket = io(BACKEND, {
  transports: ['websocket'],
  reconnection: true,
  reconnectionAttempts: Infinity,
  reconnectionDelay: 1000,
});

function App() {
  const [connected, setConnected] = useState(false);
  const [attacks, setAttacks] = useState([]);
  const [summary, setSummary] = useState({});
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('darktrace_user') || localStorage.getItem('sentinel_user');
    return saved ? JSON.parse(saved) : null;
  });

  useEffect(() => {
    fetch(`${BACKEND}/api/summary`)
      .then((response) => response.json())
      .then((data) => setSummary(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    socket.on('connect', () => {
      setConnected(true);
      console.log('[socket] connected');
    });

    socket.on('disconnect', () => {
      setConnected(false);
      console.log('[socket] disconnected');
    });

    socket.on('new_attack', (data) => {
      setAttacks((prev) => [...prev.slice(-500), data]);
      setSummary((prev) => ({
        ...prev,
        total_attacks: (prev.total_attacks || 0) + 1,
        latest_ip: data.ip,
      }));

      const risk = data.risk_score || 0;
      if (risk >= 70) {
        const label = risk >= 90 ? 'CRITICAL' : 'HIGH';
        const event = data.eventid || '';
        const msg = event.includes('login')
          ? `${label} | Login attempt from ${data.ip} | user: ${data.username || '?'} pass: ${data.password || '?'}`
          : `${label} | ${data.ip}: ${data.command}`;
        toast.warn(msg, { autoClose: 4000, position: 'bottom-right' });
      }

    });

    return () => {
      socket.off('connect');
      socket.off('disconnect');
      socket.off('new_attack');
    };
  }, []);

  const handleLogin = (profile) => {
    localStorage.setItem('darktrace_user', JSON.stringify(profile));
    setUser(profile);
  };

  const handleLogout = () => {
    localStorage.removeItem('darktrace_user');
    localStorage.removeItem('sentinel_user');
    setUser(null);
  };

  if (!user) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <Router>
      <div className="app">
        <nav className="top-nav">
          <div className="brand-block">
            <DarkTraceLogo />
            <div>
              <h1>DarkTrace</h1>
              <span>Local Security Command Center</span>
            </div>
          </div>

          <div className="nav-links">
            <NavLink to="/">Home</NavLink>
            <NavLink to="/dashboard">Dashboard</NavLink>
            <NavLink to="/terminal">Terminal</NavLink>
            <NavLink to="/logs">Logs</NavLink>
            <NavLink to="/analytics">Analytics</NavLink>
            <NavLink to="/map">Live Map</NavLink>
          </div>

          <div className="nav-status">
            <span className={`status-pill ${connected ? 'online' : 'offline'}`}>
              {connected ? 'Connected' : 'Disconnected'}
            </span>
            <button className="logout-btn" onClick={handleLogout} type="button">
              Logout
            </button>
          </div>
        </nav>

        <main>
          <Routes>
            <Route
              path="/"
              element={<LandingPage connected={connected} attacks={attacks} summary={summary} />}
            />

            <Route
              path="/dashboard"
              element={(
                <Dashboard
                  connected={connected}
                  attacks={attacks}
                  summary={summary}
                  socket={socket}
                  backendUrl={BACKEND}
                />
              )}
            />

            <Route
              path="/terminal"
              element={(
                <div className="dashboard-grid terminal-only">
                  <section className="terminal-panel">
                    <Terminal socket={socket} backendUrl={BACKEND} />
                  </section>
                </div>
              )}
            />

            <Route path="/logs" element={<LogTable backendUrl={BACKEND} />} />
            <Route path="/analytics" element={<Analytics backendUrl={BACKEND} />} />
            <Route
              path="/map"
              element={(
                <div className="map-page">
                  <AttackMap attacks={attacks} backendUrl={BACKEND} />
                </div>
              )}
            />
          </Routes>
        </main>

        <ToastContainer theme="dark" position="bottom-right" />
      </div>
    </Router>
  );
}

export default App;
