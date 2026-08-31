import { Link } from 'react-router-dom';
import { IconLogo } from '../components/Icons';
import { HOME_FOR_ROLE, useAuth } from '../context/AuthContext';

export default function NotFound() {
  const { user } = useAuth();
  const home = user ? HOME_FOR_ROLE[user.role] || '/home' : '/';

  return (
    <div className="auth-shell">
      <div className="auth-card center">
        <div className="auth-brand">
          <span className="logo-mark">
            <IconLogo width={30} height={30} />
          </span>
          <h1 style={{ fontSize: '1.3rem' }}>Page not found</h1>
          <p className="tagline">
            That page does not exist, or you do not have access to it.
          </p>
        </div>
        <Link to={home} className="btn btn-primary btn-block">
          Go back
        </Link>
      </div>
    </div>
  );
}
