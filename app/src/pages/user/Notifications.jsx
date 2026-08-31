import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { errorMessage } from '../../api/client';
import { notificationApi } from '../../api/endpoints';
import UserShell from '../../components/UserShell';
import { Alert, EmptyState, Spinner } from '../../components/Ui';
import { IconBell, IconCheck, IconClock, IconShield, IconWrench } from '../../components/Icons';
import { useToast } from '../../context/ToastContext';
import { timeAgo } from '../../lib/format';

const ICONS = {
  report_submitted: <IconClock width={18} height={18} />,
  report_validated: <IconShield width={18} height={18} />,
  report_assigned: <IconWrench width={18} height={18} />,
  report_in_progress: <IconWrench width={18} height={18} />,
  report_resolved: <IconCheck width={18} height={18} />,
  task_assigned: <IconWrench width={18} height={18} />,
  task_verified: <IconCheck width={18} height={18} />,
  task_rejected: <IconBell width={18} height={18} />,
};

export default function Notifications() {
  const navigate = useNavigate();
  const toast = useToast();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await notificationApi.list({ page_size: 50 });
      setItems(data.items);
    } catch (err) {
      setError(errorMessage(err, 'Could not load your notifications.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function open(notification) {
    if (!notification.is_read) {
      try {
        await notificationApi.markRead(notification.notification_id);
        setItems((current) =>
          current.map((item) =>
            item.notification_id === notification.notification_id
              ? { ...item, is_read: true }
              : item,
          ),
        );
      } catch {
        /* reading is best-effort - navigation still proceeds */
      }
    }
    if (notification.report_id) navigate(`/my-reports/${notification.report_id}`);
  }

  async function markAll() {
    try {
      await notificationApi.markAllRead();
      setItems((current) => current.map((item) => ({ ...item, is_read: true })));
      toast.success('All notifications marked as read.');
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  const unread = items.filter((item) => !item.is_read).length;

  return (
    <UserShell
      title="Notifications"
      back
      plainHeader
      action={
        unread > 0 ? (
          <button type="button" className="btn btn-ghost btn-sm" onClick={markAll}>
            Mark all read
          </button>
        ) : null
      }
    >
      {error && (
        <div className="mb-3">
          <Alert tone="error">{error}</Alert>
        </div>
      )}

      {loading ? (
        <Spinner label="Loading notifications" />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<IconBell />}
          title="No notifications yet"
          description="Updates about your reports will show up here."
        />
      ) : (
        <div className="stack">
          {items.map((notification) => (
            <button
              key={notification.notification_id}
              type="button"
              className="list-row"
              onClick={() => open(notification)}
              style={
                notification.is_read
                  ? undefined
                  : { borderLeft: '3px solid var(--teal-600)', background: 'var(--teal-50)' }
              }
            >
              <span className="row-icon">
                {ICONS[notification.type] || <IconBell width={18} height={18} />}
              </span>
              <div className="grow">
                <div className="row-title">
                  {notification.title || 'RouteSathi update'}
                  {!notification.is_read && (
                    <span
                      aria-label="Unread"
                      style={{
                        display: 'inline-block',
                        width: 7,
                        height: 7,
                        borderRadius: '50%',
                        background: 'var(--teal-600)',
                        marginLeft: 7,
                        verticalAlign: 'middle',
                      }}
                    />
                  )}
                </div>
                <div className="row-meta">{notification.message}</div>
                <div className="tiny muted mt-2">{timeAgo(notification.created_at)}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </UserShell>
  );
}
