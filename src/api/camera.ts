import { apiUrl } from './client';

export interface CameraResolution {
  width: number;
  height: number;
}

export async function getCameraResolution(): Promise<CameraResolution> {
  const res = await fetch(apiUrl('/camera/resolution'));
  if (!res.ok) {
    throw new Error(`Failed to get camera resolution: ${res.statusText}`);
  }
  const data = await res.json();
  return { width: data.width, height: data.height };
}

async function cameraZoomPost(path: string): Promise<{ ok: boolean; message: string }> {
  const res = await fetch(apiUrl(path), { method: 'POST' });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail ?? `Camera zoom: ${res.statusText}`);
  }
  return data;
}

/** Connect / verify camera for zoom control (ISAPI). */
export async function cameraZoomConnect(): Promise<{ ok: boolean; message: string }> {
  return cameraZoomPost('/camera/zoom/connect');
}

/** Start zoom in (continuous). Call cameraZoomStop to stop. */
export async function cameraZoomIn(): Promise<{ ok: boolean; message: string }> {
  return cameraZoomPost('/camera/zoom/in');
}

/** Start zoom out (continuous). Call cameraZoomStop to stop. */
export async function cameraZoomOut(): Promise<{ ok: boolean; message: string }> {
  return cameraZoomPost('/camera/zoom/out');
}

/** Stop zoom movement. */
export async function cameraZoomStop(): Promise<{ ok: boolean; message: string }> {
  return cameraZoomPost('/camera/zoom/stop');
}
