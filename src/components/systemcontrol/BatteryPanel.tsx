import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { BatteryStatus } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface BatteryPanelProps {
  batteryStatus: BatteryStatus;
}

export function BatteryPanel({ batteryStatus }: BatteryPanelProps) {
  const { t } = useTranslation();

  const lowBattery = batteryStatus.currentPercent < 10;

  return (
    <DataPanel
      title={t('systemControl.battery', 'Battery')}
      status={batteryStatus.currentPercent > 20 ? 'stable' : batteryStatus.currentPercent > 10 ? 'warning' : 'error'}
    >
      <div className="space-y-2 text-sm">
        <DataRow
          label={t('battery.capacity')}
          value={batteryStatus.totalCapacityKwh.toFixed(1)}
          unit="kWh"
        />
        <DataRow
          label={t('battery.percent')}
          value={batteryStatus.currentPercent}
          unit="%"
        />
        <DataRow
          label={t('battery.chargeTime')}
          value={batteryStatus.estimatedTimeToChargeMinutes}
          unit="min"
        />
        <DataRow
          label={t('systemControl.battery.alarms', 'Alarms')}
          value={lowBattery ? t('systemControl.lowBattery', 'Low Battery') : t('systemControl.none', 'None')}
          warning={lowBattery}
        />
      </div>
    </DataPanel>
  );
}

