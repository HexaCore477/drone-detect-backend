import { cn } from '@/lib/utils';
import type { LaserStatus } from '@/types/telemetry';
import type { DetectedBalloon } from '@/types/tracking';

interface CameraOverlaysProps {
  balloons: DetectedBalloon[];
  laserStatus: LaserStatus;
  centerX: number;
  centerY: number;
  width: number;
  height: number;
}

export function CameraOverlays({ 
  balloons, 
  laserStatus, 
  centerX, 
  centerY,
  width,
  height 
}: CameraOverlaysProps) {
  const scaleX = (x: number) => (x / width) * 100;
  const scaleY = (y: number) => (y / height) * 100;
  
  const targetBalloon = balloons.find(b => b.isTarget);
  
  const lockStatusColors = {
    searching: 'border-yellow-500',
    acquiring: 'border-yellow-400 animate-pulse',
    locked: 'border-green-500',
    lost: 'border-red-500 animate-pulse',
  };

  const lockStatusText = {
    searching: 'SEARCHING',
    acquiring: 'ACQUIRING',
    locked: 'LOCKED',
    lost: 'LOCK LOST',
  };

  return (
    <div className="absolute inset-0 z-10 pointer-events-none">
      {/* Crosshair / Aiming Reticle */}
      <div className="absolute inset-0">
        {/* Horizontal line */}
        <div
          className="absolute left-0 right-0 h-px bg-primary/40"
          style={{ top: `${scaleY(centerY)}%` }}
        />
        {/* Vertical line */}
        <div
          className="absolute top-0 bottom-0 w-px bg-primary/40"
          style={{ left: `${scaleX(centerX)}%` }}
        />
        
        {/* Target reticle circles */}
        <div
          className={cn(
            'absolute w-16 h-16 border-2 rounded-full -translate-x-1/2 -translate-y-1/2 transition-colors',
            lockStatusColors[laserStatus.lockStatus]
          )}
          style={{
            left: `${scaleX(centerX)}%`,
            top: `${scaleY(centerY)}%`,
          }}
        />
        <div
          className={cn(
            'absolute w-8 h-8 border rounded-full -translate-x-1/2 -translate-y-1/2 transition-colors',
            lockStatusColors[laserStatus.lockStatus]
          )}
          style={{
            left: `${scaleX(centerX)}%`,
            top: `${scaleY(centerY)}%`,
          }}
        />
        
        {/* Center dot */}
        <div
          className={cn(
            'absolute w-2 h-2 rounded-full -translate-x-1/2 -translate-y-1/2',
            laserStatus.lockStatus === 'locked' ? 'bg-green-500 shadow-[0_0_10px_#22c55e]' : 'bg-red-500'
          )}
          style={{
            left: `${scaleX(centerX)}%`,
            top: `${scaleY(centerY)}%`,
          }}
        />
      </div>

      {/* Laser Spot Indicator (when laser is on and locked) */}
      {laserStatus.enabled && laserStatus.lockStatus === 'locked' && targetBalloon && (
        <div
          className="absolute w-4 h-4 -translate-x-1/2 -translate-y-1/2"
          style={{
            left: `${scaleX(targetBalloon.centerX)}%`,
            top: `${scaleY(targetBalloon.centerY)}%`,
          }}
        >
          <div className="absolute inset-0 bg-red-500 rounded-full animate-pulse opacity-80 shadow-[0_0_20px_#ef4444,0_0_40px_#ef4444]" />
          <div className="absolute inset-1 bg-white rounded-full opacity-90" />
        </div>
      )}

      {/* Lock Status Display */}
      <div className="absolute top-3 right-3 z-20">
        <div className={cn(
          'px-3 py-1.5 rounded border backdrop-blur-sm font-mono text-xs font-bold uppercase',
          {
            'bg-yellow-500/20 border-yellow-500/50 text-yellow-400': laserStatus.lockStatus === 'searching' || laserStatus.lockStatus === 'acquiring',
            'bg-green-500/20 border-green-500/50 text-green-400': laserStatus.lockStatus === 'locked',
            'bg-red-500/20 border-red-500/50 text-red-400 animate-pulse': laserStatus.lockStatus === 'lost',
          }
        )}>
          {lockStatusText[laserStatus.lockStatus]}
        </div>
      </div>

      {/* Target Marker for tracked target */}
      {targetBalloon && (
        <div
          className="absolute -translate-x-1/2 -translate-y-1/2"
          style={{
            left: `${scaleX(targetBalloon.centerX)}%`,
            top: `${scaleY(targetBalloon.centerY)}%`,
          }}
        >
          {/* Corner brackets */}
          <div className="relative w-20 h-20">
            {/* Top-left */}
            <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-green-500" />
            {/* Top-right */}
            <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-green-500" />
            {/* Bottom-left */}
            <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-green-500" />
            {/* Bottom-right */}
            <div className="absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 border-green-500" />
          </div>
          
          {/* Target label */}
          <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 whitespace-nowrap">
            <span className="px-1.5 py-0.5 bg-green-500/20 border border-green-500/50 rounded text-[10px] font-mono text-green-400">
              TGT-001
            </span>
          </div>
        </div>
      )}

      {/* Balloon bounding boxes */}
      {balloons.map((b) => (
        <div
          key={b.id}
          className={cn(
            'absolute border-2 box-border',
            b.isTarget ? 'border-transparent' : 'border-yellow-500/70'
          )}
          style={{
            left: `${scaleX(b.boundingBox.x)}%`,
            top: `${scaleY(b.boundingBox.y)}%`,
            width: `${scaleX(b.boundingBox.width)}%`,
            height: `${scaleY(b.boundingBox.height)}%`,
          }}
        />
      ))}
    </div>
  );
}
