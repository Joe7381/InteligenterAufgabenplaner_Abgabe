import React, { useState } from 'react';
import { API_BASE } from './config';

function Register({ onRegister }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    try {
      const res = await fetch(API_BASE + '/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (res.ok) {
        setSuccess('Registrierung erfolgreich! Bitte einloggen.');
        if (onRegister) onRegister();
      } else {
        setError(data.detail || 'Registrierung fehlgeschlagen');
      }
    } catch (err) {
      setError('Serverfehler');
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
        <button type="submit" className="btn btn-primary" style={{width: '100%'}}>Registrieren</button>
      </form>
      {error && <div style={{color: 'var(--danger)', marginTop: '1rem'}}>{error}</div>}
      {success && <div style={{color: 'var(--success)', marginTop: '1rem'}}>{success}</div>}
    </div>
  );
}

export default Register;
