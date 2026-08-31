import { useState } from 'react';
import { errorMessage } from '../api/client';
import { maintenanceApi } from '../api/endpoints';
import { useToast } from '../context/ToastContext';
import { IconImage } from './Icons';

/**
 * Opens the resolution photo for a task.
 *
 * The image itself is private, so the URL is fetched on demand: with S3
 * configured that is a presigned URL, otherwise a URL carrying a short-lived
 * scoped media token.  Either way the browser can load it without needing an
 * Authorization header.
 */
export default function ResolutionImageLink({ taskId, label = 'View resolution photo', inline = false }) {
  const toast = useToast();
  const [url, setUrl] = useState('');
  const [busy, setBusy] = useState(false);

  async function reveal() {
    setBusy(true);
    try {
      const link = await maintenanceApi.resolutionLink(taskId);
      setUrl(link.url);
      if (!inline) window.open(link.url, '_blank', 'noopener');
    } catch (err) {
      toast.error(errorMessage(err, 'Could not open the resolution photo.'));
    } finally {
      setBusy(false);
    }
  }

  if (inline && url) {
    return (
      <img
        src={url}
        alt={`Resolution photo for task ${taskId}`}
                  className="evidence-image"
      />
    );
  }

  return (
    <button
      type="button"
      className="btn btn-secondary btn-sm btn-block"
      onClick={reveal}
      disabled={busy}
    >
      <IconImage width={15} height={15} /> {busy ? 'Opening…' : label}
    </button>
  );
}
