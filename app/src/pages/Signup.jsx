import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { Alert, Field } from '../components/Ui';
import { IconLogo } from '../components/Icons';
import { useAuth } from '../context/AuthContext';

export default function Signup() {
  const { signUp } = useAuth();
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: '',
    email: '',
    phone: '',
    password: '',
    confirm: '',
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const update = (key) => (event) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');

    if (form.password.length < 8) {
      setError('Choose a password with at least 8 characters.');
      return;
    }
    if (form.password !== form.confirm) {
      setError('The two passwords do not match.');
      return;
    }

    setBusy(true);
    try {
      await signUp({
        name: form.name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim() || null,
        password: form.password,
        role: 'USER',
      });
      navigate('/home', { replace: true });
    } catch (err) {
      setError(errorMessage(err, 'Could not create your account. Please try again.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="logo-mark">
            <IconLogo width={30} height={30} />
          </span>
          <h1 style={{ fontSize: '1.35rem' }}>Create your account</h1>
          <p className="tagline">Report barriers. Track the fix.</p>
        </div>

        <form onSubmit={handleSubmit} noValidate>
          {error && (
            <div className="mb-3">
              <Alert tone="error">{error}</Alert>
            </div>
          )}

          <Field label="Full name" htmlFor="name">
            <input
              id="name"
              className="input"
              required
              minLength={2}
              autoComplete="name"
              value={form.name}
              onChange={update('name')}
              placeholder="Ananya Sen"
            />
          </Field>

          <Field label="Email address" htmlFor="email">
            <input
              id="email"
              className="input"
              type="email"
              required
              autoComplete="email"
              value={form.email}
              onChange={update('email')}
              placeholder="you@example.com"
            />
          </Field>

          <Field label="Phone number" htmlFor="phone" hint="Optional. Used for repair updates.">
            <input
              id="phone"
              className="input"
              type="tel"
              autoComplete="tel"
              value={form.phone}
              onChange={update('phone')}
              placeholder="+91 98300 00000"
            />
          </Field>

          <Field label="Password" htmlFor="password" hint="At least 8 characters.">
            <input
              id="password"
              className="input"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={form.password}
              onChange={update('password')}
            />
          </Field>

          <Field label="Confirm password" htmlFor="confirm">
            <input
              id="confirm"
              className="input"
              type="password"
              required
              autoComplete="new-password"
              value={form.confirm}
              onChange={update('confirm')}
            />
          </Field>

          <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={busy}>
            {busy ? 'Creating your account…' : 'Create account'}
          </button>
        </form>

        <p className="small center mt-3 muted">
          Already registered? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
