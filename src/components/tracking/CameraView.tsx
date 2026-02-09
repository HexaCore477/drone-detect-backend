import type { DetectedBalloon } from '@/types/tracking';
import type { LaserStatus } from '@/types/telemetry';
import { CameraOverlays } from '@/components/tracking/overlays/CameraOverlays';
import { getCameraResolution } from '@/api';
import { useTranslation } from 'react-i18next';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

interface CameraViewProps {
  balloons: DetectedBalloon[];
  centerX?: number;
  centerY?: number;
  showCrosshair?: boolean;
  laserStatus?: LaserStatus;
}

const DEFAULT_WIDTH = 1280;
const DEFAULT_HEIGHT = 720;

const defaultLaserStatus: LaserStatus = {
  enabled: false,
  power: 0,
  frequency: 0,
  lockStatus: 'searching',
};

export function CameraView({ 
  balloons,
  centerX: centerXProp,
  centerY: centerYProp,
  showCrosshair = true,
  laserStatus = defaultLaserStatus
}: CameraViewProps) {
  const { t } = useTranslation();
  const [retryKey, setRetryKey] = useState(0);
  const [resolution, setResolution] = useState<{ width: number; height: number } | null>(null);

  const imgRef = useRef<HTMLImageElement>(null);

  const streamUrl = useMemo(() => {
    const API_BASE = import.meta.env.DEV ? '' : 'http://localhost:8000';
    return `${API_BASE}/api/stream`;
  }, []);

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
    return () => {
      if (imgRef.current) {
        imgRef.current.src = '';
      }
    };
  }, []);

  return (
    <div className="w-full h-full flex items-center justify-center bg-black rounded overflow-hidden border border-border">
      {/* Inner container: same aspect ratio as camera - prevents stretching, overlays align */}
      <div
        className="relative max-w-full max-h-full bg-black"
        style={{ aspectRatio: width / height }}
      >
        {/* Camera feed: MJPEG stream - fills container, no stretch */}
        <img
          key={retryKey}
          src={streamUrl}
          className="w-full h-full object-contain block"
          onError={(e) => {
            console.error('Stream error, retrying...');
            setTimeout(() => setRetryKey(prev => prev + 1), 2000);
          }}
        />

        {/* Camera Overlays: target marker, laser spot, lock status */}
        {showCrosshair && (
          <CameraOverlays
            balloons={balloons}
            laserStatus={laserStatus}
            centerX={centerX}
            centerY={centerY}
            width={width}
            height={height}
          />
        )}

        {/* Frame Counter / Timestamp Overlay */}
        <div className="absolute bottom-2 left-2 z-10 font-mono text-[10px] text-primary/70 bg-black/50 px-2 py-0.5 rounded">
          {new Date().toISOString().replace('T', ' ').slice(0, 19)}
        </div>

        {/* Resolution indicator */}
        <div className="absolute bottom-2 right-2 font-mono text-[10px] text-muted-foreground bg-black/50 px-2 py-0.5 rounded">
          {width}×{height}
        </div>
      </div>
    </div>
  );
}
