import { apiUrl } from './client';

export interface MovePayload {
  pan: number;
  tilt: number;
}

export type PtuDirection =
  | 'left'
  | 'right'
  | 'up'
  | 'down'
  | 'pause'
  | 'left-up'
  | 'left-down'
  | 'right-up'
  | 'right-down';

export interface ConnectPayload {
  port: string;
  baud?: number;
}

export interface PtuConnectStatus {
  connected: boolean;
}

async function ptuPost(path: string, body?: object): Promise<void> {
  const res = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `${path} failed`);
  }
}

export async function getPtuPorts(): Promise<string[]> {
  const res = await fetch(apiUrl('/ptu/getports'));
  if (!res.ok) {
    throw new Error(`Failed to get PTU ports: ${res.statusText}`);
  }
  const data = await res.json();
  return data.ports ?? [];
}

export async function ptuMoveAbsolute(payload: MovePayload): Promise<void> {
  await ptuPost('/ptu/move/absolute', payload);
}

export async function ptuMoveRelative(payload: MovePayload): Promise<void> {
  await ptuPost('/ptu/move/relative', payload);
}

export async function ptuDirection(direction: PtuDirection): Promise<void> {
  await ptuPost(`/ptu/direction/${direction}`);
}

export async function ptuConnect(payload: ConnectPayload): Promise<void> {
  await ptuPost('/ptu/connect', { port: payload.port, baud: payload.baud ?? 9600 });
}

export async function ptuDisconnect(): Promise<void> {
  await ptuPost('/ptu/disconnect');
}

export async function getPtuConnectStatus(): Promise<PtuConnectStatus> {
  const res = await fetch(apiUrl('/ptu/connect-status'));
  if (!res.ok) {
    throw new Error(`Failed to get PTU connect status: ${res.statusText}`);
  }
  const data = await res.json();
  return { connected: Boolean(data.connected) };
}

export interface PtuPosition {
  pan: number;
  tilt: number;
}

/** Query PTU for actual position (H10E/H20E). On 503 falls back to cached position. */
export async function queryPtuPosition(): Promise<PtuPosition> {
  const res = await fetch(apiUrl('/ptu/position/query'));
  if (res.ok) {
    const data = await res.json();
    return { pan: Number(data.pan), tilt: Number(data.tilt) };
  }
  if (res.status === 503) {
    const cached = await fetch(apiUrl('/ptu/position/cached'));
    if (cached.ok) {
      const data = await cached.json();
      return { pan: Number(data.pan), tilt: Number(data.tilt) };
    }
  }
  throw new Error(`PTU position query failed: ${res.statusText}`);
}
