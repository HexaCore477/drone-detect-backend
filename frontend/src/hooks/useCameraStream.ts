import { useCallback, useEffect, useRef, useState } from 'react';

const getDefaultWsUrl = () => {
  const envUrl = import.meta.env.VITE_WS_STREAM_URL;
  if (envUrl) return envUrl;
  const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
  const port = import.meta.env.VITE_WS_STREAM_PORT ?? '8000';
  const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${host}:${port}/api/stream/ws`;
};

export interface CameraStreamState {
  frameSrc: string | null;
  error: string | null;
  status: 'connecting' | 'connected' | 'disconnected' | 'error';
  timestamp: string | null;
}

export function useCameraStream(wsUrl?: string) {
  const url = wsUrl ?? getDefaultWsUrl();
  const [state, setState] = useState<CameraStreamState>({
    frameSrc: null,
    error: null,
    status: 'disconnected',
    timestamp: null,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const lastUrlRef = useRef<string | null>(null);
  const hasReceivedFrame = useRef(false);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 10;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setState((s) => ({ ...s, status: 'connecting', error: null }));
    console.log('[useCameraStream] Connecting to', url);
    const ws = new WebSocket(url);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      hasReceivedFrame.current = false;
      console.log('[useCameraStream] WebSocket connected');
      setState((s) => ({ ...s, status: 'connected', error: null }));
    };

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        const blob = new Blob([event.data], { type: 'image/jpeg' });
        const url = URL.createObjectURL(blob);
        if (lastUrlRef.current) URL.revokeObjectURL(lastUrlRef.current);
        lastUrlRef.current = url;
        if (hasReceivedFrame.current && imgRef.current) {
          imgRef.current.src = url;
        } else {
          hasReceivedFrame.current = true;
          setState((s) => ({ ...s, frameSrc: url, error: null }));
        }
      } else {
        try {
          const data = JSON.parse(event.data as string);
          if (data.error) {
            console.error('[useCameraStream] Server error:', data.error);
            setState((s) => ({ ...s, error: data.error, status: 'error' }));
          }
        } catch (e) {
          console.warn('[useCameraStream] Parse error:', e);
        }
      }
    };

    ws.onerror = () => {
      console.error('[useCameraStream] WebSocket error');
      setState((s) => ({ ...s, status: 'error', error: 'WebSocket error' }));
    };

    ws.onclose = () => {
      console.log('[useCameraStream] WebSocket closed');
      wsRef.current = null;
      setState((s) => ({ ...s, status: 'disconnected' }));

      if (reconnectAttempts.current < maxReconnectAttempts) {
        reconnectAttempts.current += 1;
        reconnectTimeoutRef.current = setTimeout(connect, 2000);
      }
    };

    wsRef.current = ws;
  }, [url]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = undefined;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (lastUrlRef.current) {
      URL.revokeObjectURL(lastUrlRef.current);
      lastUrlRef.current = null;
    }
    hasReceivedFrame.current = false;
    setState({
      frameSrc: null,
      error: null,
      status: 'disconnected',
      timestamp: null,
    });
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { ...state, connect, disconnect, imgRef };
}
