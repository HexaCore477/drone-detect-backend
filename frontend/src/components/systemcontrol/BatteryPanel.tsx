import { useState } from 'react';
import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { BatteryStatus } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface BatteryPanelProps {
  batteryStatus: BatteryStatus;
}

export function BatteryPanel({ batteryStatus }: BatteryPanelProps) {
  const { t } = useTranslation();

  const [alarm, setAlarm] = useState(false);

  const lowBattery = batteryStatus.currentPercent < 10 || alarm;

  const status =
    batteryStatus.currentPercent > 20 ? 'stable' : batteryStatus.currentPercent > 10 ? 'warning' : 'error';

  return (
    <DataPanel
      title={t('systemControl.battery', 'Battery')}
      status={status}
    >
      <div className="space-y-2 text-sm">
        {/* Capacity (read-only) */}
        <DataRow
          label={t('battery.capacity')}
          value={batteryStatus.totalCapacityKwh.toFixed(1)}
          unit="kWh"
        />

        {/* Charge % (read-only) */}
        <DataRow
          label={t('battery.percent')}
          value={batteryStatus.currentPercent}
          unit="%"
        />

        {/* Estimated charge time (read-only) */}
        <DataRow
          label={t('battery.chargeTime')}
          value={batteryStatus.estimatedTimeToChargeMinutes}
          unit="min"
        />

        {/* Alarm: configurable Yes/No */}
        <DataRow
          label={t('systemControl.battery.alarms', 'Alarms')}
          value={lowBattery ? t('systemControl.yes', 'Yes') : t('systemControl.no', 'No')}
          warning={lowBattery}
        />
        <button
          type="button"
          className="w-full text-right text-[11px] text-muted-foreground hover:text-primary"
          onClick={() => setAlarm((v) => !v)}
        >
          {alarm ? t('systemControl.clearAlarm', 'Clear Alarm') : t('systemControl.raiseAlarm', 'Raise Alarm')}
        </button>
      </div>
    </DataPanel>
  );
}

