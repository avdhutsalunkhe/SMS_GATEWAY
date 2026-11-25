import { useMemo, useState } from 'react';
import { StatusBadge } from './StatusBadge';

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'pending', label: 'Pending' },
  { id: 'processing', label: 'Processing' },
  { id: 'sent', label: 'Sent' },
  { id: 'failed', label: 'Failed' },
];

function formatTimestamp(isoString) {
  if (!isoString) return '—';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return isoString;
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function SmsLogsTable({ logs, counts, loading, onRefresh }) {
  const [statusFilter, setStatusFilter] = useState('all');

  const filteredLogs = useMemo(() => {
    if (statusFilter === 'all') return logs;
    return logs.filter((log) => log.status === statusFilter);
  }, [logs, statusFilter]);

  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">
            Live SMS Queue &amp; Logs
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Showing recent 50 messages • Auto-polls every 5 seconds
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
            {FILTERS.map((f) => {
              const active = statusFilter === f.id;
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setStatusFilter(f.id)}
                  className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                    active
                      ? 'bg-white text-slate-900 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {f.label}
                </button>
              );
            })}
          </div>

          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
          >
            <svg
              className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M21 12a9 9 0 1 1-3.2-6.9" />
              <polyline points="21 3 21 9 15 9" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 divide-x divide-y divide-slate-200 border-b border-slate-200 sm:grid-cols-4 sm:divide-y-0">
        <div className="px-5 py-3">
          <p className="text-xs text-slate-500">Pending</p>
          <p className="mt-0.5 text-lg font-semibold text-amber-600">
            {counts.pending ?? 0}
          </p>
        </div>
        <div className="px-5 py-3">
          <p className="text-xs text-slate-500">Processing</p>
          <p className="mt-0.5 text-lg font-semibold text-slate-700">
            {counts.processing ?? 0}
          </p>
        </div>
        <div className="px-5 py-3">
          <p className="text-xs text-slate-500">Sent</p>
          <p className="mt-0.5 text-lg font-semibold text-emerald-600">
            {counts.sent ?? 0}
          </p>
        </div>
        <div className="px-5 py-3">
          <p className="text-xs text-slate-500">Failed</p>
          <p className="mt-0.5 text-lg font-semibold text-rose-600">
            {counts.failed ?? 0}
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/70 text-xs font-medium text-slate-500">
              <th className="px-5 py-3">Recipient</th>
              <th className="px-4 py-3">Project</th>
              <th className="px-4 py-3">Message</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-center">Retries</th>
              <th className="px-5 py-3 text-right">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredLogs.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-5 py-10 text-center text-xs text-slate-500"
                >
                  {logs.length === 0
                    ? 'No SMS messages queued yet.'
                    : `No ${statusFilter} messages in recent logs.`}
                </td>
              </tr>
            ) : (
              filteredLogs.map((log) => (
                <tr key={log.message_id} className="hover:bg-slate-50/60">
                  <td className="whitespace-nowrap px-5 py-3 font-mono text-xs font-medium text-slate-900">
                    {log.to}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-xs text-slate-600">
                    {log.project_name}
                  </td>
                  <td className="max-w-xs px-4 py-3 text-xs text-slate-700">
                    <p className="truncate" title={log.message}>
                      {log.message}
                    </p>
                    {log.error && (
                      <p
                        className="mt-0.5 truncate text-[11px] text-rose-600"
                        title={log.error}
                      >
                        {log.error}
                      </p>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-3">
                    <StatusBadge status={log.status} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-3 text-center text-xs text-slate-600">
                    {log.retry_count ?? 0}
                  </td>
                  <td className="whitespace-nowrap px-5 py-3 text-right text-xs text-slate-500">
                    {formatTimestamp(log.sent_at || log.created_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
