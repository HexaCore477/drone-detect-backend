import { DataPanel, DataRow, DataGrid, DataCell } from '@/components/ui/DataPanel';
import type {
  LaserStatus,
  WaterCoolingStatus,
  BatteryStatus,
} from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface IndicatorPanelsProps {
  laserStatus: LaserStatus;
  waterCooling: WaterCoolingStatus;
  battery: BatteryStatus;
}

export function IndicatorPanels({
  laserStatus,
  waterCooling,
  battery,
}: IndicatorPanelsProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-3">
      {/* Laser Status */}
      <DataPanel
        title={t('laser.title', 'Laser')}
        status={laserStatus.on ? 'stable' : 'warning'}
      >
        <div className="space-y-2">
          <DataRow
            label={t('laser.status', 'Status')}
            value={laserStatus.on ? t('laser.on', 'On') : t('laser.off', 'Off')}
          />
          <DataRow label={t('laser.power', 'Power')} value={laserStatus.powerPercent} unit="%" />
          <DataRow label={t('laser.frequency', 'Frequency')} value={laserStatus.frequencyHz} unit="Hz" />
        </div>
      </DataPanel>

      {/* Water Cooling */}
      <DataPanel
        title={t('cooling.title', 'Water Cooling')}
        status={waterCooling.on && waterCooling.currentTempC < waterCooling.thresholdTempC ? 'stable' : 'warning'}
      >
        <div className="space-y-2">
          <DataRow
            label={t('cooling.status', 'Status')}
            value={waterCooling.on ? t('cooling.on', 'On') : t('cooling.off', 'Off')}
          />
          <DataRow
            label={t('cooling.temp', 'Current')}
            value={waterCooling.currentTempC.toFixed(1)}
            unit="°C"
          />
          <DataRow
            label={t('cooling.threshold', 'Threshold')}
            value={waterCooling.thresholdTempC.toFixed(1)}
            unit="°C"
          />
        </div>
      </DataPanel>

      {/* Battery */}
      <DataPanel
        title={t('battery.title', 'Battery')}
        status={battery.currentPercent > 20 ? 'stable' : battery.currentPercent > 10 ? 'warning' : 'error'}
      >
        <div className="space-y-2">
          <DataRow label={t('battery.capacity', 'Capacity')} value={battery.totalCapacityKwh.toFixed(2)} unit="kWh" />
          <DataRow label={t('battery.percent', 'Charge')} value={battery.currentPercent} unit="%" />
          <DataRow
            label={t('battery.chargeTime', 'Est. charge time')}
            value={battery.estimatedTimeToChargeMinutes}
            unit="min"
          />
        </div>
      </DataPanel>

    </div>
  );
}
