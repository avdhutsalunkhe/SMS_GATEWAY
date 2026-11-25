import { useCallback, useEffect, useState } from 'react';
import { fetchAdminLogs, fetchProjects } from './api/gatewayApi';
import { ApiKeyManager } from './components/ApiKeyManager';
import { Header } from './components/Header';
import { QuickTestSender } from './components/QuickTestSender';
import { SmsLogsTable } from './components/SmsLogsTable';

const POLL_INTERVAL_MS = 5000;

export default function App() {
  const [deviceOnline, setDeviceOnline] = useState(false);
  const [backendReachable, setBackendReachable] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [logs, setLogs] = useState([]);
  const [counts, setCounts] = useState({
    pending: 0,
    processing: 0,
    sent: 0,
    failed: 0,
    total: 0,
  });
  const [projects, setProjects] = useState([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [errorBanner, setErrorBanner] = useState('');

  const loadLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      const data = await fetchAdminLogs();
      setDeviceOnline(Boolean(data.device_online));
      setCounts(
        data.counts || {
          pending: 0,
          processing: 0,
          sent: 0,
          failed: 0,
          total: 0,
        },
      );
      setLogs(Array.isArray(data.logs) ? data.logs : []);
      setBackendReachable(true);
      setLastUpdated(new Date());
      setErrorBanner('');
    } catch (err) {
      setBackendReachable(false);
      setDeviceOnline(false);
      setErrorBanner(err.message || 'Unable to reach SMS Gateway backend');
    } finally {
      setLoadingLogs(false);
    }
  }, []);

  const loadProjects = useCallback(async () => {
    try {
      const list = await fetchProjects();
      setProjects(Array.isArray(list) ? list : []);
    } catch {
      // Handled by backendReachable status from logs polling
    }
  }, []);

  useEffect(() => {
    loadLogs();
    loadProjects();

    const timer = setInterval(() => {
      loadLogs();
    }, POLL_INTERVAL_MS);

    return () => clearInterval(timer);
  }, [loadLogs, loadProjects]);

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <Header
        deviceOnline={deviceOnline}
        backendReachable={backendReachable}
        lastUpdated={lastUpdated}
      />

      <main className="mx-auto max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        {errorBanner && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-700">
            {errorBanner}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-4">
            <QuickTestSender projects={projects} onSent={loadLogs} />
            <ApiKeyManager projects={projects} onProjectCreated={loadProjects} />
          </div>

          <div className="lg:col-span-8">
            <SmsLogsTable
              logs={logs}
              counts={counts}
              loading={loadingLogs}
              onRefresh={loadLogs}
            />
          </div>
        </div>
      </main>
    </div>
  );
}
