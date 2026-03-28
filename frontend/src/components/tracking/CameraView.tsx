import type { DetectedBalloon } from '@/types/tracking';
import { getCameraResolution } from '@/api';
import { useTranslation } from 'react-i18next';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

interface CameraViewProps {
  balloons: DetectedBalloon[];
  centerX?: number;
  centerY?: number;
  showCrosshair?: boolean;
}

const DEFAULT_WIDTH = 1280;
const DEFAULT_HEIGHT = 720;

function getStreamWsUrl(): string {
  const host = window.location.hostname;
  const port = import.meta.env.DEV ? '8000' : window.location.port || '8000';
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${host}:${port}/api/stream/ws`;
}

export function CameraView({ 
  balloons,
  centerX: centerXProp,
  centerY: centerYProp,
  showCrosshair = true 
}: CameraViewProps) {
  const { t } = useTranslation();
  const [resolution, setResolution] = useState<{ width: number; height: number } | null>(null);

  const imgRef = useRef<HTMLImageElement>(null);
  const prevBlobUrlRef = useRef<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const width = resolution?.width ?? DEFAULT_WIDTH;
  const height = resolution?.height ?? DEFAULT_HEIGHT;

  const centerX = centerXProp ?? width / 2;
  const centerY = centerYProp ?? height / 2;

  const fetchResolution = useCallback(async () => {
    try {
      const res = await getCameraResolution();
      setResolution({ width: res.width, height: res.height });
    } catch (err) {
      console.warn('Could not fetch camera resolution, using defaults:', err);
      setResolution(null);
    }
  }, []);

  useEffect(() => {
    fetchResolution();
  }, [fetchResolution]);

  useEffect(() => {
    let active = true;

    function connect() {
      if (!active) return;
      const wsUrl = getStreamWsUrl();
      const ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;

      ws.onmessage = (event) => {
        if (!(event.data instanceof ArrayBuffer)) return;
        const blob = new Blob([event.data], { type: 'image/jpeg' });
        const url = URL.createObjectURL(blob);

        if (imgRef.current) {
          imgRef.current.src = url;
        }

        if (prevBlobUrlRef.current) {
          URL.revokeObjectURL(prevBlobUrlRef.current);
        }
        prevBlobUrlRef.current = url;
      };

      ws.onclose = () => {
        if (!active) return;
        reconnectTimerRef.current = setTimeout(connect, 1000);
      };

      ws.onerror = () => {
        ws.close();
      };
    }

    connect();

    return () => {
      active = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) wsRef.current.close();
      if (prevBlobUrlRef.current) URL.revokeObjectURL(prevBlobUrlRef.current);
    };
  }, []);

  const scaleX = (x: number) => (x / width) * 100;
  const scaleY = (y: number) => (y / height) * 100;

  return (
    <div className="w-full h-full flex items-center justify-center bg-black rounded overflow-hidden border border-border">
      {/* Inner container: same aspect ratio as camera - prevents stretching, overlays align */}
      <div
        className="relative max-w-full max-h-full bg-black"
        style={{ aspectRatio: width / height }}
      >
        {/* Camera feed: rendered from WebSocket JPEG frames via Blob URL */}
        <img
          ref={imgRef}
          className="w-full h-full object-contain block"
          alt="camera stream"
        />

        {/* Crosshair / Target Center */}
        {showCrosshair && (
          <div className="absolute inset-0 z-10 pointer-events-none">
            {/* Horizontal line */}
            <div
              className="absolute left-0 right-0 h-px bg-primary/50"
              style={{ top: `${scaleY(centerY)}%` }}
            />
            {/* Vertical line */}
            <div
              className="absolute top-0 bottom-0 w-px bg-primary/50"
              style={{ left: `${scaleX(centerX)}%` }}
            />
            {/* Center circle */}
            <div
              className="absolute w-8 h-8 border-2 border-green-500 rounded-full -translate-x-1/2 -translate-y-1/2"
              style={{
                left: `${scaleX(centerX)}%`,
                top: `${scaleY(centerY)}%`,
              }}
            />
            {/* Inner dot */}
            <div
              className="absolute w-2 h-2 bg-red-500 rounded-full -translate-x-1/2 -translate-y-1/2 shadow-[0_0_10px_hsl(var(--primary))]"
              style={{
                left: `${scaleX(centerX)}%`,
                top: `${scaleY(centerY)}%`,
              }}
            />
          </div>
        )}

        {/* Frame Counter / Timestamp Overlay */}
        <div className="absolute bottom-2 left-2 z-10 font-mono text-[10px] text-primary/70 bg-black/50 px-2 py-0.5 rounded">
          {new Date().toISOString().replace('T', ' ').slice(0, 19)}
        </div>

        {/* Resolution indicator */}
        <div className="absolute bottom-2 right-2 font-mono text-[10px] text-muted-foreground bg-black/50 px-2 py-0.5 rounded">
          {width}×{height}
        </div>

        {/* Balloon bounding boxes (from tracking WebSocket) */}
        {balloons.map((b) => (
          <div
            key={b.id}
            className="absolute border-2 border-red-500 box-border z-10 pointer-events-none"
            style={{
              left: `${scaleX(b.boundingBox.x)}%`,
              top: `${scaleY(b.boundingBox.y)}%`,
              width: `${scaleX(b.boundingBox.width)}%`,
              height: `${scaleY(b.boundingBox.height)}%`,
            }}
          />
        ))}

        {/* Prediction points (500ms-ahead position for each balloon) */}
        {balloons.map((b) => {
          const predX = b.predictedCenterX ?? b.centerX;
          const predY = b.predictedCenterY ?? b.centerY;
          return (
            <div
              key={`pred-${b.id}`}
              className="absolute w-5 h-5 border-2 border-cyan-400 bg-cyan-400/50 rounded-full -translate-x-1/2 -translate-y-1/2 z-20 pointer-events-none"
              style={{
                left: `${scaleX(predX)}%`,
                top: `${scaleY(predY)}%`,
                boxShadow: '0 0 8px rgba(34, 211, 238, 0.8)',
              }}
              title={t('camera.predicted', '{{id}} predicted (500ms)', { id: b.id })}
            />
          );
        })}
      </div>
    </div>
  );
}
