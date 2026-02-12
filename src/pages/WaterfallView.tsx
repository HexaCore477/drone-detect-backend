import type { LogEntry, PTUState, KalmanState, DetectedBalloon } from '@/types/tracking';
import type { KalmanFilterData } from '@/hooks/useBalloonTracking';
import { DetectionEventsLog } from '@/components/operation/DetectionEventsLog';
import { TrackingStatusLog } from '@/components/operation/TrackingStatusLog';
import { SystemLog } from '@/components/operation/SystemLog';
import { KalmanFilterLog } from '@/components/operation/KalmanFilterLog';
import { PtuCommandsLog } from '@/components/operation/PtuCommandsLog';

interface WaterfallViewProps {
  logs: LogEntry[];
  ptuState: PTUState;
  kalmanState: KalmanState;
  balloons?: DetectedBalloon[];
  balloonTimestamp?: number | null;
  kalmanData?: KalmanFilterData | null;
}

export function WaterfallView({ logs, ptuState, kalmanState, balloons = [], balloonTimestamp = null, kalmanData = null }: WaterfallViewProps) {
  return (
    <div className="h-full overflow-y-auto p-4 grid grid-cols-2 gap-4">
      {/* Left column: Detection + Tracking */}
      <div className="flex flex-col gap-4">
        <DetectionEventsLog logs={logs} balloons={balloons} balloonTimestamp={balloonTimestamp} />
        <TrackingStatusLog
          logs={logs}
          balloons={balloons}
          balloonTimestamp={balloonTimestamp}
          kalmanData={kalmanData}
        />
      </div>

      {/* Right column: Kalman + PTU Commands */}
      <div className="flex flex-col gap-4">
        <KalmanFilterLog logs={logs} kalmanData={kalmanData} kalmanTimestamp={balloonTimestamp} />
        <PtuCommandsLog logs={logs} />
      </div>

      {/* Bottom: System Log spanning both columns */}
      <div className="col-span-2">
        <SystemLog logs={logs} />
      </div>
    </div>
  );
}
