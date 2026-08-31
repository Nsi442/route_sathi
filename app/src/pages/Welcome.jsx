import { Link } from 'react-router-dom';
import { IconLogo, IconMap, IconReport, IconShield } from '../components/Icons';

/** First-run screen introducing the product and the three portals. */
export default function Welcome() {
  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="logo-mark">
            <IconLogo width={30} height={30} />
          </span>
          <h1 style={{ fontSize: '1.6rem' }}>RouteSathi</h1>
          <p className="tagline">Accessible Places. Better Access.</p>
        </div>

        <div className="stack mb-4">
          <Feature
            icon={<IconMap width={18} height={18} />}
            title="Find accessible places"
            body="Ramps, step-free entrances, accessible toilets and parking near you."
          />
          <Feature
            icon={<IconReport width={18} height={18} />}
            title="Report what blocks you"
            body="Send a photo, a location and a severity. Track the repair to completion."
          />
          <Feature
            icon={<IconShield width={18} height={18} />}
            title="Verified by the authority"
            body="Every report is reviewed, prioritised and assigned to a maintenance team."
          />
        </div>

        <Link to="/signup" className="btn btn-primary btn-lg btn-block mb-2">
          Create an account
        </Link>
        <Link to="/login" className="btn btn-secondary btn-block">
          I already have an account
        </Link>

        <p className="tiny muted center mt-3">
          Authority and maintenance staff sign in with credentials issued by the
          municipal administrator.
        </p>
      </div>
    </div>
  );
}

function Feature({ icon, title, body }) {
  return (
    <div className="row" style={{ alignItems: 'flex-start', gap: 12 }}>
      <span className="choice-icon" style={{ width: 34, height: 34, borderRadius: 10 }}>
        {icon}
      </span>
      <div>
        <div className="strong" style={{ fontSize: '0.92rem' }}>
          {title}
        </div>
        <div className="small muted">{body}</div>
      </div>
    </div>
  );
}
