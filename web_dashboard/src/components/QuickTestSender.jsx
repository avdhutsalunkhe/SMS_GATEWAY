import { useEffect, useState } from 'react';
import { sendTestSms } from '../api/gatewayApi';

export function QuickTestSender({ projects, onSent }) {
  const [to, setTo] = useState('');
  const [message, setMessage] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [priority, setPriority] = useState(3);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState(null);

  useEffect(() => {
    if (!apiKey && projects.length > 0) {
      setApiKey(projects[0].api_key);
    }
  }, [projects, apiKey]);

  async function handleSubmit(event) {
    event.preventDefault();
    setFeedback(null);
    setSubmitting(true);

    try {
      const res = await sendTestSms({ to, message, apiKey, priority });
      setFeedback({
        type: 'success',
        text: `Queued (${res.message_id}). Device ${
          res.device_online ? 'is online — dispatching shortly' : 'is offline — waiting in queue'
        }.`,
      });
      setMessage('');
      if (onSent) {
        await onSent();
      }
    } catch (err) {
      setFeedback({
        type: 'error',
        text: err.message || 'Failed to send test SMS',
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-slate-900">Quick Test Sender</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          Queue a test SMS through <span className="font-mono">/api/v1/send-sms</span>.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3.5">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-700">
            Phone Number (+91 or E.164)
          </label>
          <input
            type="text"
            required
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="+919876543210"
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
          />
        </div>

        <div>
          <div className="mb-1 flex items-center justify-between">
            <label className="block text-xs font-medium text-slate-700">
              Project API Key (X-API-Key)
            </label>
            {projects.length > 0 && (
              <select
                aria-label="Select project API key"
                value={projects.some((p) => p.api_key === apiKey) ? apiKey : ''}
                onChange={(e) => {
                  if (e.target.value) setApiKey(e.target.value);
                }}
                className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600 focus:outline-none"
              >
                <option value="">Pick project…</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.api_key}>
                    {p.name}
                  </option>
                ))}
              </select>
            )}
          </div>
          <input
            type="text"
            required
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sms_..."
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
          />
        </div>

        <div>
          <div className="mb-1 flex items-center justify-between">
            <label className="block text-xs font-medium text-slate-700">Message</label>
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <span>Priority:</span>
              <select
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                className="rounded border border-slate-200 bg-white px-1.5 py-0.5 text-xs text-slate-700 focus:outline-none"
              >
                <option value={5}>5 (Highest)</option>
                <option value={4}>4</option>
                <option value={3}>3 (Normal)</option>
                <option value={2}>2</option>
                <option value={1}>1 (Lowest)</option>
              </select>
            </div>
          </div>
          <textarea
            required
            rows={3}
            maxLength={1600}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Your verification code is 482910."
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
          />
          <p className="mt-1 text-right text-[11px] text-slate-400">
            {message.length} / 1600 chars
          </p>
        </div>

        {feedback && (
          <div
            className={`rounded-lg border px-3 py-2 text-xs ${
              feedback.type === 'success'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                : 'border-rose-200 bg-rose-50 text-rose-700'
            }`}
          >
            {feedback.text}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? 'Queuing SMS…' : 'Send Test SMS'}
        </button>
      </form>
    </section>
  );
}
