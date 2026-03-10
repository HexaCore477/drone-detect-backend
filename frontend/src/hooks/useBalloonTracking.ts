import { useEffect, useRef, useState } from 'react';
import type { DetectedBalloon } from '@/types/tracking';

export interface KalmanFilterData {
  trackId: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  predX: number;
  predY: number;
  measurementX: number;
  measurementY: number;
}

interface TrackingMessage {
  timestamp: number;
  balloons: DetectedBalloon[];
  ptuPan?: number | null;
  ptuTilt?: number | null;
  kalman?: KalmanFilterData | null;
}

const getDefaultTrackingWsUrl = () => {
  const host = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
  const port = import.meta.env.VITE_WS_STREAM_PORT ?? '8000';
  const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${host}:${port}/api/tracking/ws`;
};

export function useBalloonTracking(wsUrl?: string) {
  const url = wsUrl ?? getDefaultTrackingWsUrl();
  const [balloons, setBalloons] = useState<DetectedBalloon[]>([]);
  const [ptuPan, setPtuPan] = useState<number | null>(null);
  const [ptuTilt, setPtuTilt] = useState<number | null>(null);
  const [lastTimestamp, setLastTimestamp] = useState<number | null>(null);
  const [kalmanData, setKalmanData] = useState<KalmanFilterData | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    console.log('[useBalloonTracking] Connecting to WebSocket:', url);
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[useBalloonTracking] WebSocket connected successfully');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as TrackingMessage;
        if (Array.isArray(data.balloons)) {
          if (typeof data.timestamp === 'number') setLastTimestamp(data.timestamp);
          // Log detection results
          console.log('[useBalloonTracking] Detection update:', {
            timestamp: new Date(data.timestamp).toISOString(),
            timestampMs: data.timestamp,
            balloonCount: data.balloons.length,
            balloons: data.balloons.map((b) => {
              const predX = (b as any).predictedCenterX;
              const predY = (b as any).predictedCenterY;
              const conf = (b as any).confidence;
              return {
                id: b.id,
                color: b.color,
                size: b.size,
                center: `(${b.centerX.toFixed(1)}, ${b.centerY.toFixed(1)})`,
                bbox: `[${b.boundingBox.x.toFixed(1)}, ${b.boundingBox.y.toFixed(1)}, ${b.boundingBox.width.toFixed(1)}, ${b.boundingBox.height.toFixed(1)}]`,
                predicted: (predX != null && predY != null)
                  ? `(${Number(predX).toFixed(1)}, ${Number(predY).toFixed(1)})`
                  : null,
                isTarget: b.isTarget,
                confidence: conf ?? 0,
              };
            }),
          });
          setBalloons(data.balloons);
          if (typeof data.ptuPan === 'number') {
            setPtuPan(data.ptuPan);
          }
          if (typeof data.ptuTilt === 'number') {
            setPtuTilt(data.ptuTilt);
          }
          if (data.kalman && typeof data.kalman.trackId === 'string') {
            setKalmanData(data.kalman as KalmanFilterData);
          } else {
            setKalmanData(null);
          }
        } else {
          console.warn('[useBalloonTracking] Invalid balloons array, clearing');
          setBalloons([]);
          setKalmanData(null);
        }
      } catch (e) {
        console.warn('[useBalloonTracking] Parse error', e);
      }
    };

    ws.onerror = (error) => {
      console.error('[useBalloonTracking] WebSocket error:', error);
    };

    ws.onclose = (event) => {
      console.log('[useBalloonTracking] WebSocket closed:', {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
      });
      wsRef.current = null;
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [url]);

  return { balloons, ptuPan, ptuTilt, lastTimestamp, kalmanData };
}

