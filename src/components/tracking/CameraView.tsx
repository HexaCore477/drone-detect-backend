import { cn } from '@/lib/utils';
import type { DetectedBalloon } from '@/types/tracking';

interface CameraViewProps {
  balloons: DetectedBalloon[];
  centerX: number;
  centerY: number;
  showGrid?: boolean;
  showCrosshair?: boolean;
}

export function CameraView({ 
  balloons, 
  centerX = 640, 
  centerY = 360,
  showGrid = true,
  showCrosshair = true 
}: CameraViewProps) {
  // Simulated camera resolution
  const width = 1280;
  const height = 720;
  
  const scaleX = (x: number) => (x / width) * 100;
  const scaleY = (y: number) => (y / height) * 100;

  return (
    <div className="relative w-full h-full bg-black rounded overflow-hidden border border-border">
      {/* Grid Pattern */}
      {showGrid && (
        <div className="absolute inset-0 grid-pattern opacity-30" />
      )}
      
      {/* Simulated camera feed placeholder */}
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-muted-foreground/30 text-lg font-mono">CAMERA FEED</span>
      </div>

      {/* CRT Overlay */}
      <div className="crt-overlay" />

      {/* Crosshair / Target Center */}
      {showCrosshair && (
        <>
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
        </>
      )}

      {/* Detected Balloons */}
      {balloons.map((balloon) => (
        <div key={balloon.id}>
          {/* Bounding Box */}
          <div 
            className={cn(
              'absolute border-2',
              balloon.isTarget ? 'border-tactical-red' : 'border-tactical-cyan',
              balloon.isTarget && 'animate-pulse'
            )}
            style={{
              left: `${scaleX(balloon.boundingBox.x)}%`,
              top: `${scaleY(balloon.boundingBox.y)}%`,
              width: `${scaleX(balloon.boundingBox.width)}%`,
              height: `${scaleY(balloon.boundingBox.height)}%`,
            }}
          >
            {/* Corner brackets */}
            <div className="absolute -top-0.5 -left-0.5 w-3 h-3 border-t-2 border-l-2 border-inherit" />
            <div className="absolute -top-0.5 -right-0.5 w-3 h-3 border-t-2 border-r-2 border-inherit" />
            <div className="absolute -bottom-0.5 -left-0.5 w-3 h-3 border-b-2 border-l-2 border-inherit" />
            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 border-b-2 border-r-2 border-inherit" />
          </div>

          {/* Center Point */}
          <div 
            className={cn(
              'absolute w-1.5 h-1.5 rounded-full -translate-x-1/2 -translate-y-1/2',
              balloon.isTarget ? 'bg-tactical-red shadow-[0_0_8px_hsl(var(--status-error))]' : 'bg-tactical-cyan'
            )}
            style={{
              left: `${scaleX(balloon.centerX)}%`,
              top: `${scaleY(balloon.centerY)}%`,
            }}
          />

          {/* Label */}
          <div 
            className={cn(
              'absolute font-mono text-[10px] px-1 -translate-x-1/2',
              balloon.isTarget ? 'text-tactical-red bg-tactical-red/20' : 'text-tactical-cyan bg-tactical-cyan/20'
            )}
            style={{
              left: `${scaleX(balloon.centerX)}%`,
              top: `${scaleY(balloon.boundingBox.y) - 4}%`,
            }}
          >
            {balloon.color.toUpperCase()}-{balloon.size.toUpperCase()}
            {balloon.isTarget && ' [TGT]'}
          </div>
        </div>
      ))}

      {/* Frame Counter / Timestamp Overlay */}
      <div className="absolute bottom-2 left-2 font-mono text-[10px] text-primary/70 bg-black/50 px-2 py-0.5 rounded">
        {new Date().toISOString().replace('T', ' ').slice(0, 19)}
      </div>

      {/* Resolution indicator */}
      <div className="absolute bottom-2 right-2 font-mono text-[10px] text-muted-foreground bg-black/50 px-2 py-0.5 rounded">
        {width}×{height}
      </div>
    </div>
  );
}
