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
