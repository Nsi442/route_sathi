/**
 * Status badges.
 *
 * One vocabulary for every portal so a "Needs Review" chip looks identical on
 * the citizen app and the authority table.
 */

const TONES = {
  // Report status
  Submitted: 'blue',
  'Under Review': 'amber',
  Assigned: 'violet',
  'In Progress': 'teal',
  Resolved: 'green',

  // Validation
  'Needs Review': 'amber',
  Valid: 'green',
  Invalid: 'red',

  // Severity
  Low: 'green',
  Medium: 'amber',
  High: 'red',
  Critical: 'red',

  // Facility status
  Verified: 'green',
  Available: 'teal',
  Blocked: 'red',
  Inactive: 'slate',

  // Task status
  Completed: 'blue',
  Rejected: 'red',
};

export function badgeTone(value) {
  return TONES[value] || 'slate';
}

export default function Badge({ value, tone, dot = false, children, className = '' }) {
  if (!value && !children) return <span className="muted">—</span>;
  const resolved = tone || badgeTone(value);
  return (
    <span className={`badge badge-${resolved} ${className}`.trim()}>
      {dot && <span className="badge-dot" aria-hidden="true" />}
      {children || value}
    </span>
  );
}

/** Severity chip with an explicit label for screen readers. */
export function SeverityBadge({ value }) {
  return (
    <Badge value={value} dot>
      <span className="sr-only">Severity: </span>
      {value}
    </Badge>
  );
}

export function PriorityBadge({ predicted, final }) {
  if (final) {
    return (
      <Badge value={final} dot>
        <span className="sr-only">Confirmed priority: </span>
        {final}
      </Badge>
    );
  }
  if (predicted) {
    return (
      <Badge value={predicted} tone="slate">
        <span className="sr-only">Recommended priority: </span>
        {predicted} <span className="tiny">(suggested)</span>
      </Badge>
    );
  }
  return <span className="muted small">Not set</span>;
}
