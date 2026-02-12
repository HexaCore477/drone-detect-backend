import { apiUrl } from './client';

export async function startOperation(): Promise<void> {
  const res = await fetch(apiUrl('/view/start_operation'), { method: 'POST' });
  if (!res.ok) {
    throw new Error(`start_operation failed: ${res.statusText}`);
  }
}

export async function stopOperation(): Promise<void> {
  const res = await fetch(apiUrl('/view/stop_operation'), { method: 'POST' });
  if (!res.ok) {
    throw new Error(`stop_operation failed: ${res.statusText}`);
  }
}

export async function startWaterfall(): Promise<void> {
  const res = await fetch(apiUrl('/view/start_waterfall'), { method: 'POST' });
  if (!res.ok) {
    throw new Error(`start_waterfall failed: ${res.statusText}`);
  }
}

export async function stopWaterfall(): Promise<void> {
  const res = await fetch(apiUrl('/view/stop_waterfall'), { method: 'POST' });
  if (!res.ok) {
    throw new Error(`stop_waterfall failed: ${res.statusText}`);
  }
}
