import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { initials } from '../lib/format';
import { IconLogo, IconLogout, IconMenu } from './Icons';

/**
 * Desktop shell for the authority and maintenance portals: dark navy sidebar,
 * white top bar, light content canvas.  Collapses to a drawer under 900px.
 */
export default function ConsoleShell({ portal, navItems, title, subtitle, actions, children }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const handleSignOut = () => {
    signOut();
    navigate('/login', { replace: true });
  };

  return (
    <div className="console">
      <a className="skip-link" href="#console-main">
        Skip to main content
      </a>

      {drawerOpen && (
        <div
          className="console-scrim"
          role="presentation"
          onClick={() => setDrawerOpen(false)}
        />
      )}

      <aside className={`console-sidebar ${drawerOpen ? 'is-open' : ''}`.trim()}>
        <div className="console-brand">
          <span className="logo-mark">
            <IconLogo width={22} height={22} />
          </span>
          <div>
            <div className="name">RouteSathi</div>
            <div className="portal">{portal}</div>
          </div>
        </div>

        <nav className="console-nav" aria-label={`${portal} navigation`}>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'is-active' : '')}
              onClick={() => setDrawerOpen(false)}
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="console-user">
          <span className="avatar" aria-hidden="true">
            {initials(user?.name)}
          </span>
          <div className="grow" style={{ minWidth: 0 }}>
            <div className="who truncate">{user?.name}</div>
            <div className="role truncate">{user?.organisation || user?.team || user?.role}</div>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ color: '#94a3b8' }}
            onClick={handleSignOut}
            aria-label="Sign out"
            title="Sign out"
          >
            <IconLogout width={17} height={17} />
          </button>
        </div>
      </aside>

      <div className="console-main">
        <header className="console-topbar">
          <button
            type="button"
            className="console-mobile-toggle"
            onClick={() => setDrawerOpen((open) => !open)}
            aria-label="Toggle navigation"
            aria-expanded={drawerOpen}
          >
            <IconMenu width={19} height={19} />
          </button>
          <div className="grow" style={{ minWidth: 0 }}>
            <h1 className="truncate">{title}</h1>
            {subtitle && <div className="sub truncate">{subtitle}</div>}
          </div>
          {actions}
        </header>

        <main id="console-main" className="console-content">
          {children}
        </main>
      </div>
    </div>
  );
}
