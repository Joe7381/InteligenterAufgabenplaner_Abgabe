import React, { useState } from 'react';
import { API_BASE } from './config';

function Login({ onLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const res = await fetch(API_BASE + '/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (res.ok && data.access_token) {
        localStorage.setItem('access_token', data.access_token);
        if (onLogin) onLogin(data.access_token);
      } else {
        // Falls Rate Limit (429) oder anderer Fehler: Zeige Detail-Nachricht vom Backend
        setError(data.detail || 'Login fehlgeschlagen');
      }
    } catch (err) {
      setError('Verbindung zum Server fehlgeschlagen.');
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label">E-Mail</label>
          <input 
            type="email" 
            className="form-input"
            value={email} 
            onChange={e => setEmail(e.target.value)} 
            required 
          />
        </div>
        <div className="form-group">
          <label className="form-label">Passwort</label>
          <input 
            type="password" 
            className="form-input"
            value={password} 
            onChange={e => setPassword(e.target.value)} 
            required 
          />
        </div>
        <button type="submit" className="btn btn-primary" style={{width: '100%'}}>Login</button>
      </form>
      {error && <div style={{color: 'var(--danger)', marginTop: '1rem'}}>{error}</div>}
    </div>
  );
}

export default Login;
