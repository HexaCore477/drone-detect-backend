import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { WaterCoolingStatus } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface CoolingSystemPanelProps {
  coolingStatus: WaterCoolingStatus;
}

export function CoolingSystemPanel({ coolingStatus }: CoolingSystemPanelProps) {
  const { t } = useTranslation();

  const overThreshold = coolingStatus.currentTempC > coolingStatus.thresholdTempC;

  return (
    <DataPanel
      title={t('systemControl.cooling', 'Cooling System')}
      status={coolingStatus.on ? 'stable' : 'warning'}
    >
      <div className="space-y-2 text-sm">
        <DataRow
          label={t('systemControl.cooling.onOff', 'On/Off')}
          value={coolingStatus.on ? t('camera.on') : t('camera.off')}
        />
        <DataRow
          label={t('systemControl.cooling.currentTemp', 'Current Temp')}
          value={coolingStatus.currentTempC.toFixed(1)}
          unit="°C"
        />
        <DataRow
          label={t('systemControl.cooling.alarm', 'Alarm')}
          value={
            overThreshold
              ? t('systemControl.alarm', 'High Temp')
              : t('systemControl.none', 'None')
          }
          warning={overThreshold}
        />
      </div>
    </DataPanel>
  );
}

