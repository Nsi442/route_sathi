import { IconChevronLeft, IconChevronRight, IconInbox, IconSearch } from './Icons';

/** Small presentational primitives reused across the three portals. */

export function Spinner({ label = 'Loading' }) {
  return (
    <div className="loading-row" role="status">
      <span className="spinner" aria-hidden="true" />
      <span>{label}…</span>
    </div>
  );
}

export function EmptyState({ title, description, action, icon }) {
  return (
    <div className="empty">
      <span className="empty-icon">{icon || <IconInbox />}</span>
      <h3>{title}</h3>
      {description && <p className="small">{description}</p>}
      {action}
    </div>
  );
}

export function Alert({ tone = 'info', children }) {
  if (!children) return null;
  return (
    <div className={`alert alert-${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      <span>{children}</span>
    </div>
  );
}

export function SearchInput({ value, onChange, placeholder = 'Search…', ...rest }) {
  return (
    <div className="search">
      <IconSearch width={17} height={17} />
      <input
        type="search"
        className="input"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        {...rest}
      />
    </div>
  );
}

export function Field({ label, hint, error, htmlFor, children }) {
  return (
    <div className="field">
      {label && (
        <label className="label" htmlFor={htmlFor}>
          {label}
        </label>
      )}
      {children}
      {error ? (
        <div className="hint" style={{ color: 'var(--red-700)' }}>
          {error}
        </div>
      ) : (
        hint && <div className="hint">{hint}</div>
      )}
    </div>
  );
}

export function StatCard({ label, value, icon, accent = 'teal', hint }) {
  return (
    <div className={`stat-card accent-${accent}`}>
      <div className="stat-top">
        <span className="stat-label">{label}</span>
        {icon && <span className="stat-icon">{icon}</span>}
      </div>
      <span className="stat-value">{value}</span>
      {hint && <span className="tiny muted">{hint}</span>}
    </div>
  );
}

export function Pagination({ page, pages, total, pageSize, onChange }) {
  if (!total) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  return (
    <div className="pagination">
      <span>
        Showing <strong>{from}</strong>–<strong>{to}</strong> of <strong>{total}</strong>
      </span>
      <div className="pages">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          <IconChevronLeft width={15} height={15} /> Previous
        </button>
        <span className="small">
          Page {page} of {pages}
        </span>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          Next <IconChevronRight width={15} height={15} />
        </button>
      </div>
    </div>
  );
}

export function Modal({ title, onClose, children, footer }) {
  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="modal">
        <div className="card-header">
          <h2>{title}</h2>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="card-body">{children}</div>
        {footer && <div className="card-header" style={{ borderTop: '1px solid var(--line)', borderBottom: 'none' }}>{footer}</div>}
      </div>
    </div>
  );
}

export function BarList({ items, emptyLabel = 'No data yet' }) {
  if (!items?.length) return <p className="muted small">{emptyLabel}</p>;
  const max = Math.max(...items.map((item) => item.count), 1);
  return (
    <div className="bars">
      {items.map((item) => (
        <div className="bar-row" key={item.key}>
          <span className="bar-label truncate" title={item.key}>
            {item.key}
          </span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${(item.count / max) * 100}%` }} />
          </span>
          <span className="bar-value">{item.count}</span>
        </div>
      ))}
    </div>
  );
}
