import { useRef, useState } from 'react';
import { errorMessage } from '../api/client';
import { authorityApi } from '../api/endpoints';
import { Alert } from './Ui';
import { IconFile, IconUpload } from './Icons';

/**
 * Bulk report import.
 *
 * Lives on the authority dashboard (the first page of the portal), not on the
 * reports list.  Posts the file to `POST /api/authority/reports/upload`, which
 * validates every row and returns
 * `{ totalRows, successfulRows, failedRows, errors }`.
 */
export default function CsvUpload({ onImported }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [fileName, setFileName] = useState('');

  async function upload(file) {
    if (!file) return;
    if (!/\.(csv|txt)$/i.test(file.name)) {
      setError('Choose a .csv file exported from your reporting system.');
      return;
    }
    setError('');
    setResult(null);
    setFileName(file.name);
    setBusy(true);
    setProgress(0);
    try {
      const data = await authorityApi.uploadCsv(file, (event) => {
        if (event.total) setProgress(Math.round((event.loaded / event.total) * 100));
      });
      setResult(data);
      if (data.successfulRows > 0 && onImported) onImported(data);
    } catch (err) {
      setError(errorMessage(err, 'The CSV could not be imported.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <h2>Import Reports from CSV</h2>
          <div className="card-title-sub">
            Optional. For reports collected outside the app.
          </div>
        </div>
      </div>

      <div className="card-body">
        <div className="alert alert-info mb-3" style={{ display: 'block' }}>
          <strong>Citizen reports arrive here automatically.</strong> Anything
          submitted in the RouteSathi app appears in{' '}
          <strong>Reports</strong> the moment it is sent — nothing to upload.
          <div className="tiny mt-2">
            Use this only to bring in reports gathered elsewhere: a field survey
            spreadsheet, an older complaints register, or a partner NGO&apos;s
            export. Both sources land in the same reports list and are told apart
            by the <code>source</code> column.
          </div>
        </div>

        <div
          className={`upload-panel ${dragging ? 'is-dragging' : ''}`.trim()}
          onDragOver={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            upload(event.dataTransfer.files?.[0]);
          }}
        >
          <span className="upload-icon">
            <IconUpload width={22} height={22} />
          </span>
          <h3>Drop a CSV file here</h3>
          <p className="small muted mt-2">
            Or choose a file from your computer. Maximum 5 MB, up to 5000 rows.
          </p>
          <button
            type="button"
            className="btn btn-primary mt-3"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
          >
            {busy ? `Uploading… ${progress}%` : 'Upload CSV Reports'}
          </button>
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            hidden
            onChange={(event) => {
              const file = event.target.files?.[0];
              event.target.value = '';
              upload(file);
            }}
          />
          {fileName && !busy && (
            <p className="tiny muted mt-2">
              <IconFile width={12} height={12} /> {fileName}
            </p>
          )}
        </div>

        <details className="mt-3">
          <summary className="small strong" style={{ cursor: 'pointer' }}>
            Expected columns
          </summary>
          <p className="tiny muted mt-2" style={{ lineHeight: 1.7 }}>
            <code>
              report_id, user_id, issue_type, location, latitude, longitude, severity,
              description, image_url, timestamp, validation_status, status, source
            </code>
          </p>
          <p className="tiny muted mt-2">
            <code>image_url</code> is optional and stored as text — no image is uploaded to S3
            during import, and no priority column is required.
          </p>
        </details>

        {error && (
          <div className="mt-3">
            <Alert tone="error">{error}</Alert>
          </div>
        )}

        {result && (
          <div className="mt-3">
            <Alert tone={result.failedRows > 0 ? 'warn' : 'success'}>
              Imported {result.successfulRows} of {result.totalRows} row
              {result.totalRows === 1 ? '' : 's'}
              {result.failedRows > 0 ? `; ${result.failedRows} rejected.` : '.'}
            </Alert>

            <div className="import-summary">
              <div className="box">
                <div className="n">{result.totalRows}</div>
                <div className="k">Total rows</div>
              </div>
              <div className="box ok">
                <div className="n">{result.successfulRows}</div>
                <div className="k">Imported</div>
              </div>
              <div className="box bad">
                <div className="n">{result.failedRows}</div>
                <div className="k">Rejected</div>
              </div>
            </div>

            {result.errors?.length > 0 && (
              <div className="table-wrap mt-3" style={{ border: '1px solid var(--line)' }}>
                <table className="table">
                  <thead>
                    <tr>
                      <th style={{ width: 70 }}>Row</th>
                      <th style={{ width: 130 }}>Report ID</th>
                      <th>Reason</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.errors.map((rowError, index) => (
                      <tr key={`${rowError.row}-${index}`}>
                        <td className="mono">{rowError.row}</td>
                        <td className="mono">{rowError.reportId || '—'}</td>
                        <td style={{ color: 'var(--red-700)' }}>{rowError.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
