import { API_BASE_URL } from '../api/gatewayApi';

export function Header({ deviceOnline, backendReachable, lastUpdated }) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-lg font-semibold tracking-tight text-slate-900">
              SMS Gateway
            </h1>
            <span className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs font-medium text-slate-600">
              Admin
            </span>
          </div>
          <p className="mt-0.5 text-xs text-slate-500">
            Backend: <span className="font-mono">{API_BASE_URL}</span>
            {lastUpdated ? ` • Synced ${lastUpdated.toLocaleTimeString()}` : ''}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {!backendReachable ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-rose-200 bg-rose-50 px-3 py-1.5 text-xs font-medium text-rose-700">
              <span className="h-2 w-2 rounded-full bg-rose-500" />
              Backend Unreachable
            </div>
          ) : deviceOnline ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
              </span>
              Phone Gateway Online
            </div>
          ) : (
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-600">
              <span className="h-2 w-2 rounded-full bg-rose-500" />
              Phone Gateway Offline
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
