import React, { useState } from 'react';
import DarkTraceLogo from './DarkTraceLogo';

const LoginPage = ({ onLogin }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const submit = (event) => {
    event.preventDefault();
    onLogin({ email, name: email.split('@')[0] || 'Analyst' });
  };

  return (
    <main className="login-page">
      <section className="login-hero">
        <DarkTraceLogo size={76} className="large" />
        <h1>DarkTrace</h1>
        <p>
          Sign in to your local cyber command center for running the project,
          watching telemetry, and reviewing captured activity from one place.
        </p>
      </section>

      <form className="login-card" onSubmit={submit}>
        <div>
          <span className="eyebrow">Secure access</span>
          <h2>Sign in</h2>
          <p>Enter your analyst email to open the console.</p>
        </div>

        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            required
          />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Local access"
          />
        </label>

        <button type="submit">Enter Console</button>
      </form>
    </main>
  );
};

export default LoginPage;
