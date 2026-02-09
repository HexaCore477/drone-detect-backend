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
