import { DataPanel, DataGrid, DataCell } from '@/components/ui/DataPanel';
import type { KalmanState } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface PredictionStatePanelProps {
  kalmanState: KalmanState;
}

export function PredictionStatePanel({ kalmanState }: PredictionStatePanelProps) {
  const { t } = useTranslation();

  return (
    <DataPanel
      title={t('systemControl.prediction', 'Prediction State')}
      status={kalmanState.enabled ? 'stable' : 'warning'}
    >
      <DataGrid columns={2}>
        <DataCell
          label={t('kalman.status')}
          value={kalmanState.enabled ? t('kalman.enabled') : t('kalman.disabled')}
          variant={kalmanState.enabled ? 'success' : 'warning'}
        />
        <DataCell
          label={t('kalman.mode')}
          value={kalmanState.predicting ? t('kalman.predict') : t('kalman.update')}
          variant={kalmanState.predicting ? 'warning' : 'default'}
        />
      </DataGrid>
    </DataPanel>
  );
}

