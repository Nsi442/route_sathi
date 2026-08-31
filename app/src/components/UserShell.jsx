import { useEffect, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { notificationApi } from '../api/endpoints';
import { useAuth } from '../context/AuthContext';
import {
  IconBell,
  IconChevronLeft,
  IconHome,
  IconList,
  IconMap,
  IconReport,
  IconUser,
} from './Icons';

/** Mobile-first shell for the citizen portal: top bar + bottom tab bar. */
export default function UserShell({
  title,
  children,
  back = false,
  plainHeader = false,
  flush = false,
  narrow = false,
  action,
  hideTabs = false,
}) {
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!isAuthenticated) return undefined;
    let active = true;
    notificationApi
      .count()
      .then((data) => {
        if (active) setUnread(data.unread);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [isAuthenticated, title]);

  return (
    <div className="app-shell">
      <div className="app-frame">
        <a className="skip-link" href="#main">
          Skip to main content
        </a>
        <header className={`app-topbar ${plainHeader ? 'is-plain' : ''}`.trim()}>
          {back && (
            <button
              type="button"
              className="icon-btn"
              onClick={() => navigate(-1)}
              aria-label="Go back"
            >
              <IconChevronLeft />
            </button>
          )}
          <h1>{title}</h1>
          {action}
          {!action && (
            <button
              type="button"
              className="icon-btn"
              style={{ position: 'relative' }}
              onClick={() => navigate('/notifications')}
              aria-label={
                unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'
              }
            >
              <IconBell />
              {unread > 0 && <span className="notif-dot">{unread > 9 ? '9+' : unread}</span>}
            </button>
          )}
        </header>

        <main
          id="main"
          className={`app-main ${flush ? 'is-flush' : ''} ${narrow ? 'is-narrow' : ''}`.trim()}
        >
          {children}
        </main>

        {!hideTabs && (
          <nav className="tabbar" aria-label="Main navigation">
            <NavLink to="/home" className={({ isActive }) => (isActive ? 'is-active' : '')}>
              <IconHome width={21} height={21} />
              Home
            </NavLink>
            <NavLink to="/map" className={({ isActive }) => (isActive ? 'is-active' : '')}>
              <IconMap width={21} height={21} />
              Map
            </NavLink>
            <NavLink to="/report" className={({ isActive }) => (isActive ? 'is-active' : '')}>
              <IconReport width={21} height={21} />
              Report
            </NavLink>
            <NavLink
              to="/my-reports"
              className={({ isActive }) => (isActive ? 'is-active' : '')}
            >
              <IconList width={21} height={21} />
              Reports
            </NavLink>
            <NavLink to="/profile" className={({ isActive }) => (isActive ? 'is-active' : '')}>
              <IconUser width={21} height={21} />
              Profile
            </NavLink>
          </nav>
        )}
      </div>
    </div>
  );
}
