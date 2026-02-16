import { useEffect, useRef, useState } from 'react';

export interface PtuCommand {
  command: string;
  timestamp: number;
}

const getDefaultPtuCommandsWsUrl = () => {
  const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
  const port = import.meta.env.VITE_WS_STREAM_PORT ?? '8000';
  const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${host}:${port}/api/ptu/ws/commands`;
};

export function usePtuCommands(wsUrl?: string) {
  const url = wsUrl ?? getDefaultPtuCommandsWsUrl();
  const [commands, setCommands] = useState<PtuCommand[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      // Reset on reconnect
      setCommands([]);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as { command?: string };
        if (typeof data.command === 'string') {
          const entry: PtuCommand = {
            command: data.command,
            timestamp: Date.now(),
          };
          setCommands((prev) => [...prev.slice(-99), entry]);
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [url]);

  return { commands };
}
