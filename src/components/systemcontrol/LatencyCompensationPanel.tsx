import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { SystemStatus, KalmanState } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface LatencyCompensationPanelProps {
  systemStatus: SystemStatus;
  kalmanState: KalmanState;
}

export function LatencyCompensationPanel({
  systemStatus,
  kalmanState,
}: LatencyCompensationPanelProps) {
  const { t } = useTranslation();

  return (
    <DataPanel
      title={t('systemControl.latency', 'Latency Compensation')}
      status="stable"
    >
      <div className="space-y-2 text-sm">
        <DataRow
          label={t('tracking.latency')}
          value={systemStatus.latencyMs}
          unit="ms"
        />
        <DataRow
          label={t('systemControl.latency.enabled', 'Compensation')}
          value={kalmanState.enabled ? t('systemControl.enabled', 'Enabled') : t('systemControl.disabled', 'Disabled')}
        />
      </div>
    </DataPanel>
  );
}

