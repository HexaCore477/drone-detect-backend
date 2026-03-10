import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import { StatusBadge } from '@/components/tracking/indicators/StatusBadge';
import { useTranslation } from 'react-i18next';
import type { LaserStatus } from '@/types/telemetry';

interface LaserStatusPanelProps {
  status: LaserStatus;
}

const lockStatusLabels: Record<LaserStatus['lockStatus'], string> = {
  searching: 'SEARCHING',
  acquiring: 'ACQUIRING',
  locked: 'LOCKED',
  lost: 'LOST',
};

export function LaserStatusPanel({ status }: LaserStatusPanelProps) {
  const { t } = useTranslation();
  
  const lockVariant = {
    searching: 'warning' as const,
    acquiring: 'warning' as const,
    locked: 'on' as const,
    lost: 'error' as const,
  };
  
  return (
    <DataPanel 
      title={t('laser.title', 'Laser System')} 
      status={status.enabled ? 'stable' : 'warning'}
    >
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="data-label">{t('laser.status', 'Status')}</span>
          <StatusBadge 
            label={status.enabled ? 'ON' : 'OFF'} 
            status={status.enabled ? 'on' : 'off'} 
          />
        </div>
        <div className="flex items-center justify-between">
          <span className="data-label">{t('laser.lock', 'Lock')}</span>
          <StatusBadge 
            label={lockStatusLabels[status.lockStatus]} 
            status={lockVariant[status.lockStatus]} 
          />
        </div>
        <DataRow 
          label={t('laser.power', 'Power')} 
          value={status.power} 
          unit="%" 
          highlight={status.power >= 80}
        />
        <DataRow 
          label={t('laser.frequency', 'Frequency')} 
          value={status.frequency} 
          unit="Hz" 
        />
      </div>
    </DataPanel>
  );
}
