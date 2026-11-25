import { useState } from 'react';
import { createProject } from '../api/gatewayApi';

export function ApiKeyManager({ projects, onProjectCreated }) {
  const [name, setName] = useState('');
  const [rateLimit, setRateLimit] = useState(60);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');
  const [copiedId, setCopiedId] = useState(null);

  async function handleCreate(event) {
    event.preventDefault();
    if (!name.trim()) return;
    setError('');
    setCreating(true);
    try {
      await createProject({ name: name.trim(), rateLimitPerMin: rateLimit });
      setName('');
      setRateLimit(60);
      if (onProjectCreated) {
        await onProjectCreated();
      }
    } catch (err) {
      setError(err.message || 'Failed to create project');
    } finally {
      setCreating(false);
    }
  }

  async function handleCopy(project) {
    try {
      await navigator.clipboard.writeText(project.api_key);
      setCopiedId(project.id);
      setTimeout(() => {
        setCopiedId((current) => (current === project.id ? null : current));
      }, 1800);
    } catch {
      setError('Clipboard access denied by browser');
    }
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-slate-900">API Key Manager</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          Copy an <span className="font-mono">X-API-Key</span> or issue a key for a new app.
        </p>
      </div>

      <form onSubmit={handleCreate} className="mb-4 flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New project name (e.g. Auth OTP)"
          className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:outline-none"
        />
        <input
          type="number"
          min={1}
          max={10000}
          value={rateLimit}
          onChange={(e) => setRateLimit(Number(e.target.value))}
          title="Rate limit per minute"
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-900 focus:border-slate-400 focus:outline-none sm:w-24"
        />
        <button
          type="submit"
          disabled={creating}
          className="rounded-lg border border-slate-200 bg-slate-900 px-3.5 py-2 text-xs font-medium text-white transition hover:bg-slate-800 disabled:opacity-50"
        >
          {creating ? 'Creating…' : 'Create Key'}
        </button>
      </form>

      {error && (
        <div className="mb-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
          {error}
        </div>
      )}

      <div className="divide-y divide-slate-100 rounded-lg border border-slate-200">
        {projects.length === 0 ? (
          <p className="px-3.5 py-6 text-center text-xs text-slate-500">
            No projects loaded yet.
          </p>
        ) : (
          projects.map((project) => {
            const isCopied = copiedId === project.id;
            return (
              <div
                key={project.id}
                className="flex flex-col gap-2 px-3.5 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-xs font-semibold text-slate-900">
                      {project.name}
                    </span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
                      {project.rate_limit_per_min}/min
                    </span>
                  </div>
                  <p className="mt-1 truncate font-mono text-[11px] text-slate-500">
                    {project.api_key}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => handleCopy(project)}
                  className={`shrink-0 rounded-md border px-2.5 py-1 text-xs font-medium transition ${
                    isCopied
                      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                      : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {isCopied ? 'Copied!' : 'Copy Key'}
                </button>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}
