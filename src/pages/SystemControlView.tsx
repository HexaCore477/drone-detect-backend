import type {
  PTUState,
  KalmanState,
  SystemStatus,
  LaserStatus,
  WaterCoolingStatus,
  BatteryStatus,
} from '@/types/tracking';
import { LaserStatePanel } from '@/components/systemcontrol/LaserStatePanel';
import { CoolingSystemPanel } from '@/components/systemcontrol/CoolingSystemPanel';
import { BatteryPanel } from '@/components/systemcontrol/BatteryPanel';
import { PredictionStatePanel } from '@/components/systemcontrol/PredictionStatePanel';
import { LatencyCompensationPanel } from '@/components/systemcontrol/LatencyCompensationPanel';
import { PtuStatePanel } from '@/components/systemcontrol/PtuStatePanel';
import { CameraStatePanel } from '@/components/systemcontrol/CameraStatePanel';

interface SystemControlViewProps {
  systemStatus: SystemStatus;
  ptuState: PTUState;
  kalmanState: KalmanState;
  laserStatus: LaserStatus;
  coolingStatus: WaterCoolingStatus;
  batteryStatus: BatteryStatus;
}

export function SystemControlView({
  systemStatus,
  ptuState,
  kalmanState,
  laserStatus,
  coolingStatus,
  batteryStatus,
}: SystemControlViewProps) {
  return (
    <div className="h-full p-4 grid grid-cols-3 gap-4">
      <LaserStatePanel laserStatus={laserStatus} coolingStatus={coolingStatus} />
      <CoolingSystemPanel coolingStatus={coolingStatus} />
      <BatteryPanel batteryStatus={batteryStatus} />

      <PredictionStatePanel kalmanState={kalmanState} />
      <LatencyCompensationPanel systemStatus={systemStatus} kalmanState={kalmanState} />
      <PtuStatePanel ptuState={ptuState} systemStatus={systemStatus} />
      <CameraStatePanel systemStatus={systemStatus} />
    </div>
  );
}

