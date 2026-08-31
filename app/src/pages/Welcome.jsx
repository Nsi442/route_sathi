import { Link } from 'react-router-dom';
import {
  IconChevronRight,
  IconLogo,
  IconShield,
  IconUser,
  IconWrench,
} from '../components/Icons';

/**
 * Landing page.
 *
 * Three portals share one application, so the first decision is which one you
 * belong to. Each card routes to the sign-in form with that role preselected,
 * and the backend refuses a token if the account does not actually hold it —
 * picking a card here is a convenience, never a way in.
 */
const PORTALS = [
  {
    key: 'USER',
    className: 'is-user',
    icon: <IconUser width={24} height={24} />,
    audience: 'For everyone',
    title: 'Citizen',
    description:
      'Find ramps, step-free entrances, accessible toilets and parking near you. Report a barrier with a photo and follow it until it is fixed.',
    cta: 'Sign in or create an account',
    to: '/login?role=USER',
  },
  {
    key: 'AUTHORITY',
    className: 'is-authority',
    icon: <IconShield width={24} height={24} />,
    audience: 'Municipal staff',
    title: 'Authority',
    description:
      'Review and validate incoming reports, confirm a priority, assign a maintenance team and verify the repair before it is closed.',
    cta: 'Sign in',
    to: '/login?role=AUTHORITY',
  },
  {
    key: 'MAINTENANCE',
    className: 'is-maintenance',
    icon: <IconWrench width={24} height={24} />,
    audience: 'Field teams',
    title: 'Maintenance',
    description:
      'See the repairs assigned to you or your team, record what you found on site, and submit a photo of the finished work.',
    cta: 'Sign in',
    to: '/login?role=MAINTENANCE',
  },
];

export default function Welcome() {
  return (
    <div className="landing">
      <div className="landing-inner">
        <header className="landing-head">
          <span className="logo-mark">
            <IconLogo width={34} height={34} />
          </span>
          <h1>RouteSathi</h1>
          <p className="tagline">Accessible Places. Better Access.</p>
          <p className="blurb">
            One platform connecting the people who find accessibility barriers, the
            authority that reviews them, and the teams that fix them.
          </p>
        </header>

        <p className="landing-prompt">Choose your portal</p>

        <div className="role-grid">
          {PORTALS.map((portal) => (
            <Link key={portal.key} to={portal.to} className={`role-card ${portal.className}`}>
              <span className="role-icon">{portal.icon}</span>
              <span className="role-for">{portal.audience}</span>
              <h2>{portal.title}</h2>
              <p className="role-desc">{portal.description}</p>
              <span className="role-go">
                {portal.cta}
                <IconChevronRight width={15} height={15} />
              </span>
            </Link>
          ))}
        </div>

        <footer className="landing-foot">
          <p>
            New here? <Link to="/signup">Create a citizen account</Link> — it takes a
            minute.
          </p>
          <p style={{ marginTop: 6 }}>
            Authority and maintenance accounts are issued by the municipal
            administrator and cannot be self-registered.
          </p>
        </footer>
      </div>
    </div>
  );
}