import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { LaserStatus, WaterCoolingStatus } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface LaserStatePanelProps {
  laserStatus: LaserStatus;
  coolingStatus: WaterCoolingStatus;
}

export function LaserStatePanel({ laserStatus, coolingStatus }: LaserStatePanelProps) {
  const { t } = useTranslation();

  return (
    <DataPanel
      title={t('systemControl.laserState', 'Laser State')}
      status={laserStatus.on ? 'stable' : 'warning'}
    >
      <div className="space-y-2 text-sm">
        <DataRow
          label={t('systemControl.laser.enabled', 'Enabled')}
          value={laserStatus.on ? t('camera.on') : t('camera.off')}
        />
        <DataRow
          label={t('systemControl.laser.interlock', 'Interlock')}
          value={laserStatus.on ? t('systemControl.ok', 'OK') : t('systemControl.open', 'Open')}
        />
        <DataRow
          label={t('systemControl.laser.temp', 'Temperature')}
          value={coolingStatus.currentTempC.toFixed(1)}
          unit="°C"
        />
        <DataRow
          label={t('systemControl.laser.alarms', 'Alarms')}
          value={t('systemControl.none', 'None')}
        />
      </div>
    </DataPanel>
  );
}

