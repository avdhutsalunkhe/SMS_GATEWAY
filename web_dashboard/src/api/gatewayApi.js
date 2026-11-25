const RAW_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
export const API_BASE_URL = RAW_BASE_URL.replace(/\/+$/, '');
const ADMIN_API_KEY = import.meta.env.VITE_ADMIN_API_KEY || '';

function adminHeaders(extra = {}) {
  const headers = { ...extra };
  if (ADMIN_API_KEY) {
    headers['X-Admin-Key'] = ADMIN_API_KEY;
  }
  return headers;
}

async function handleJsonResponse(response) {
  let data = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON response body
  }

  if (!response.ok) {
    const detail =
      typeof data?.detail === 'string'
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail.map((item) => item.msg || JSON.stringify(item)).join(', ')
          : `Request failed with status ${response.status}`;
    throw new Error(detail);
  }
  return data;
}

export async function fetchAdminLogs() {
  const res = await fetch(`${API_BASE_URL}/api/v1/admin/logs`, {
    headers: adminHeaders(),
  });
  return handleJsonResponse(res);
}

export async function fetchProjects() {
  const res = await fetch(`${API_BASE_URL}/api/v1/admin/projects`, {
    headers: adminHeaders(),
  });
  return handleJsonResponse(res);
}

export async function createProject({ name, rateLimitPerMin }) {
  const res = await fetch(`${API_BASE_URL}/api/v1/admin/projects`, {
    method: 'POST',
    headers: adminHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      name,
      rate_limit_per_min: Number(rateLimitPerMin) || 60,
      is_active: true,
    }),
  });
  return handleJsonResponse(res);
}

export async function sendTestSms({ to, message, apiKey, priority = 3 }) {
  const res = await fetch(`${API_BASE_URL}/api/v1/send-sms`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey.trim(),
    },
    body: JSON.stringify({
      to: to.trim(),
      message: message.trim(),
      priority: Number(priority) || 3,
    }),
  });
  return handleJsonResponse(res);
}
