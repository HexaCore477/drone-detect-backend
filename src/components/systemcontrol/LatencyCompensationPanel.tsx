import { useState } from 'react';
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

  const [latencyMs, setLatencyMs] = useState(systemStatus.latencyMs);
  const [enabled, setEnabled] = useState(kalmanState.enabled);

  return (
    <DataPanel
      title={t('systemControl.latency', 'Latency Compensation')}
      status="stable"
    >
      <div className="space-y-2 text-sm">
        <DataRow
          label={t('tracking.latency')}
          value={latencyMs}
          unit="ms"
        />
        <div className="flex justify-end">
          <input
            type="number"
            className="w-24 bg-background border border-border rounded px-1 py-0.5 text-[11px] text-right"
            value={latencyMs}
            onChange={(e) => setLatencyMs(Number(e.target.value) || 0)}
          />
        </div>

        <DataRow
          label={t('systemControl.latency.enabled', 'Compensation')}
          value={enabled ? t('systemControl.enabled', 'Enabled') : t('systemControl.disabled', 'Disabled')}
        />
        <button
          type="button"
          className="w-full text-right text-[11px] text-muted-foreground hover:text-primary"
          onClick={() => setEnabled((v) => !v)}
        >
          {enabled ? t('systemControl.switchOff', 'Disable') : t('systemControl.switchOn', 'Enable')}
        </button>
      </div>
    </DataPanel>
  );
}

