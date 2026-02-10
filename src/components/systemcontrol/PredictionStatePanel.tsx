import { useState } from 'react';
import { DataPanel, DataGrid, DataCell } from '@/components/ui/DataPanel';
import type { KalmanState } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface PredictionStatePanelProps {
  kalmanState: KalmanState;
}

export function PredictionStatePanel({ kalmanState }: PredictionStatePanelProps) {
  const { t } = useTranslation();

  const [enabled, setEnabled] = useState(kalmanState.enabled);
  const [predicting, setPredicting] = useState(kalmanState.predicting);

  return (
    <DataPanel
      title={t('systemControl.prediction', 'Prediction State')}
      status={enabled ? 'stable' : 'warning'}
    >
      <DataGrid columns={2}>
        {/* Status + Enable/Disable under it */}
        <div className="space-y-2">
          <DataCell
            label={t('kalman.status')}
            value={enabled ? t('kalman.enabled') : t('kalman.disabled')}
            variant={enabled ? 'success' : 'warning'}
          />
          <button
            type="button"
            className="px-2 py-1 border border-border rounded bg-muted/40 hover:bg-muted/70 text-[11px] text-right"
            onClick={() => setEnabled((v) => !v)}
          >
            {enabled ? t('systemControl.switchOff', 'Disable') : t('systemControl.switchOn', 'Enable')}
          </button>
        </div>

        {/* Mode + Predict/Update under it */}
        <div className="space-y-2">
          <DataCell
            label={t('kalman.mode')}
            value={predicting ? t('kalman.predict') : t('kalman.update')}
            variant={predicting ? 'warning' : 'default'}
          />
          <button
            type="button"
            className="px-2 py-1 border border-border rounded bg-muted/40 hover:bg-muted/70 text-[11px] text-right"
            onClick={() => setPredicting((v) => !v)}
          >
            {predicting ? t('kalman.update') : t('kalman.predict')}
          </button>
        </div>
      </DataGrid>
    </DataPanel>
  );
}

