import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { errorMessage } from '../api/client';
import { Alert, Field } from '../components/Ui';
import { IconLogo } from '../components/Icons';
import { HOME_FOR_ROLE, useAuth } from '../context/AuthContext';

const PORTALS = [
  { key: 'USER', label: 'Citizen', demo: 'ananya@routesathi.app' },
  { key: 'AUTHORITY', label: 'Authority', demo: 'authority@routesathi.app' },
  { key: 'MAINTENANCE', label: 'Maintenance', demo: 'maintenance@routesathi.app' },
];

export default function Login() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [portal, setPortal] = useState('USER');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const active = PORTALS.find((item) => item.key === portal);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const user = await signIn(email.trim(), password, portal);
      const target = location.state?.from || HOME_FOR_ROLE[user.role] || '/home';
      navigate(target, { replace: true });
    } catch (err) {
      setError(errorMessage(err, 'Could not sign you in. Check your details and try again.'));
    } finally {
      setBusy(false);
    }
  }

  function useDemoAccount() {
    setEmail(active.demo);
    setPassword('Password123!');
    setError('');
  }

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="logo-mark">
            <IconLogo width={30} height={30} />
          </span>
          <h1 style={{ fontSize: '1.35rem' }}>Sign in to RouteSathi</h1>
          <p className="tagline">Accessible Places. Better Access.</p>
        </div>

        <div className="role-tabs" role="tablist" aria-label="Choose a portal">
          {PORTALS.map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={portal === item.key}
              className={portal === item.key ? 'is-active' : ''}
              onClick={() => {
                setPortal(item.key);
                setError('');
              }}
            >
              {item.label}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} noValidate>
          {error && (
            <div className="mb-3">
              <Alert tone="error">{error}</Alert>
            </div>
          )}

          <Field label="Email address" htmlFor="email">
            <input
              id="email"
              className="input"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
            />
          </Field>

          <Field label="Password" htmlFor="password">
            <input
              id="password"
              className="input"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
            />
          </Field>

          <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={busy}>
            {busy ? 'Signing in…' : `Sign in to the ${active.label} portal`}
          </button>
        </form>

        {portal === 'USER' && (
          <p className="small center mt-3 muted">
            New here? <Link to="/signup">Create a citizen account</Link>
          </p>
        )}

        <div className="demo-accounts">
          <strong>Demo {active.label.toLowerCase()} account</strong>
          <div className="mt-2">
            {active.demo} ·{' '}
            <button type="button" onClick={useDemoAccount}>
              fill this in
            </button>
          </div>
          <div className="tiny mt-2">
            Available after running <code>python scripts/seed_data.py</code>.
          </div>
        </div>
      </div>
    </div>
  );
}
