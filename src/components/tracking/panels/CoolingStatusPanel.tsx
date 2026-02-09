import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import { StatusBadge } from '@/components/tracking/indicators/StatusBadge';
import { Progress } from '@/components/ui/progress';
import { useTranslation } from 'react-i18next';
import type { CoolingStatus } from '@/types/telemetry';

interface CoolingStatusPanelProps {
  status: CoolingStatus;
}

export function CoolingStatusPanel({ status }: CoolingStatusPanelProps) {
  const { t } = useTranslation();
  
  const tempPercent = (status.currentTemp / status.thresholdTemp) * 100;
  const isOverheating = status.currentTemp >= status.thresholdTemp * 0.9;
  
  return (
    <DataPanel 
      title={t('cooling.title', 'Water Cooling')} 
      status={isOverheating ? 'warning' : status.enabled ? 'stable' : 'warning'}
    >
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="data-label">{t('cooling.system', 'System')}</span>
          <StatusBadge 
            label={status.enabled ? 'ON' : 'OFF'} 
            status={status.enabled ? 'on' : 'off'} 
          />
        </div>
        <div className="flex items-center justify-between">
          <span className="data-label">{t('cooling.pump', 'Pump')}</span>
          <StatusBadge 
            label={status.pumpRunning ? 'RUNNING' : 'STOPPED'} 
            status={status.pumpRunning ? 'active' : 'inactive'} 
          />
        </div>
        <DataRow 
          label={t('cooling.currentTemp', 'Current')} 
          value={status.currentTemp.toFixed(1)} 
          unit="°C"
          warning={isOverheating}
        />
        <DataRow 
          label={t('cooling.threshold', 'Threshold')} 
          value={status.thresholdTemp.toFixed(1)} 
          unit="°C" 
        />
        <div className="pt-1">
          <Progress 
            value={Math.min(tempPercent, 100)} 
            className="h-1.5"
          />
        </div>
      </div>
    </DataPanel>
  );
}
