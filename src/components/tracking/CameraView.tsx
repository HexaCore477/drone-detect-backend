import type { DetectedBalloon } from '@/types/tracking';
import { useTranslation } from 'react-i18next';
import { useEffect, useMemo, useRef, useState } from 'react';

interface CameraViewProps {
  balloons: DetectedBalloon[];
  centerX: number;
  centerY: number;
  showCrosshair?: boolean;
}

export function CameraView({ 
  balloons,
  centerX = 640, 
  centerY = 360,
  showCrosshair = true 
}: CameraViewProps) {
  const { t } = useTranslation();
  const [retryKey, setRetryKey] = useState(0);

  // Create ref to store reference to img element
  const imgRef = useRef<HTMLImageElement>(null);

  const streamUrl = useMemo(() => {
    const API_BASE = import.meta.env.DEV ? '' : 'http://localhost:8000'
    const STREAM_URL = `${API_BASE}/api/stream`
    // Use relative URL so Vite proxy forwards to backend (avoids CORS)
    return STREAM_URL;
  }, []);
  
  // Cleanup effect - runs on unmount
  useEffect(() => {
    console.log('CameraView mounted');
    
    return () => {
      console.log('CameraView unmounting - cleaning up stream');
      
      // Disconnect the stream by clearing src
      if (imgRef.current) {
        imgRef.current.src = '';
        console.log('Stream connection aborted');
      }
    };
  }, []); // Empty deps = runs once on mount, cleanup on unmount
  
  // Simulated camera resolution
  const width = 1280;
  const height = 720;
  
  const scaleX = (x: number) => (x / width) * 100;
  const scaleY = (y: number) => (y / height) * 100;

  return (
    <div className="relative w-full h-full bg-black rounded overflow-hidden border border-border">
      {/* Camera feed: MJPEG stream */}
      <div className="absolute inset-0 z-0 flex items-center justify-center bg-black">
        <img
          key={retryKey}
          src={streamUrl}
          className="w-full h-full object-contain"
          onError={(e) => {
            console.error('Stream error, retrying...');
            setTimeout(() => setRetryKey(prev => prev + 1), 2000);
          }}
        />
      </div>

      {/* CRT Overlay */}
      <div className="crt-overlay z-10" />

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
            className="absolute w-8 h-8 border-2 border-primary rounded-full -translate-x-1/2 -translate-y-1/2"
            style={{ 
              left: `${scaleX(centerX)}%`, 
              top: `${scaleY(centerY)}%` 
            }}
          />
          {/* Inner dot */}
          <div 
            className="absolute w-2 h-2 bg-primary rounded-full -translate-x-1/2 -translate-y-1/2 shadow-[0_0_10px_hsl(var(--primary))]"
            style={{ 
              left: `${scaleX(centerX)}%`, 
              top: `${scaleY(centerY)}%` 
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
    </div>
  );
}
