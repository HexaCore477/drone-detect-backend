import type { LogEntry, PTUState, KalmanState } from '@/types/tracking';
import { DetectionEventsLog } from '@/components/operation/DetectionEventsLog';
import { TrackingStatusLog } from '@/components/operation/TrackingStatusLog';
import { SystemLog } from '@/components/operation/SystemLog';
import { KalmanFilterLog } from '@/components/operation/KalmanFilterLog';
import { PtuCommandsLog } from '@/components/operation/PtuCommandsLog';

interface WaterfallViewProps {
  logs: LogEntry[];
  ptuState: PTUState;
  kalmanState: KalmanState;
}

export function WaterfallView({ logs, ptuState, kalmanState }: WaterfallViewProps) {
  return (
    <div className="h-full p-4 grid grid-cols-2 gap-4">
      {/* Left column: Detection + Tracking */}
      <div className="flex flex-col gap-4">
        <DetectionEventsLog logs={logs} />
        <TrackingStatusLog logs={logs} />
      </div>

      {/* Right column: Kalman + PTU Commands */}
      <div className="flex flex-col gap-4">
        <KalmanFilterLog logs={logs} />
        <PtuCommandsLog logs={logs} />
      </div>

      {/* Bottom: System Log spanning both columns */}
      <div className="col-span-2">
        <SystemLog logs={logs} />
      </div>
    </div>
  );
}
