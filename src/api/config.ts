import { apiUrl } from './client';

export interface AutoTrackingConfig {
  is_auto_tracking: boolean;
}

export async function getAutoTracking(): Promise<AutoTrackingConfig> {
  const res = await fetch(apiUrl('/config/auto-tracking'));
  if (!res.ok) {
    throw new Error(`Failed to get auto-tracking config: ${res.statusText}`);
  }
  const data = await res.json();
  return { is_auto_tracking: Boolean(data.is_auto_tracking) };
}

export async function setAutoTracking(is_auto_tracking: boolean): Promise<AutoTrackingConfig> {
  const res = await fetch(apiUrl('/config/auto-tracking'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_auto_tracking }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to set auto-tracking config');
  }
  const data = await res.json();
  return { is_auto_tracking: Boolean(data.is_auto_tracking) };
}
