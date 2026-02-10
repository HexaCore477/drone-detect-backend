import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import { useTranslation } from 'react-i18next';
import type { DroneData } from '@/types/telemetry';

interface DroneDataPanelProps {
  data: DroneData;
}

const droneTypeLabels: Record<DroneData['type'], string> = {
  'fixed-wing': 'Fixed Wing',
  'multirotor': 'Multirotor',
  'helicopter': 'Helicopter',
  'unknown': 'Unknown',
};

export function DroneDataPanel({ data }: DroneDataPanelProps) {
  const { t } = useTranslation();
  
  return (
    <DataPanel title={t('drone.title', 'Target Data')} status="stable">
      <div className="space-y-1 text-sm">
        <DataRow label={t('drone.type', 'Type')} value={droneTypeLabels[data.type]} />
        <DataRow label={t('drone.speed', 'Speed')} value={data.speed.toFixed(1)} unit="m/s" />
        <DataRow label={t('drone.distance', 'Distance')} value={data.distance.toFixed(0)} unit="m" />
        <DataRow label={t('drone.roll', 'Roll')} value={data.attitude.roll.toFixed(1)} unit="°" />
        <DataRow label={t('drone.pitch', 'Pitch')} value={data.attitude.pitch.toFixed(1)} unit="°" />
        <DataRow label={t('drone.yaw', 'Heading')} value={data.attitude.yaw.toFixed(1)} unit="°" />
      </div>
    </DataPanel>
  );
}
