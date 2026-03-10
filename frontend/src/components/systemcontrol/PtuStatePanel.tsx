import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { PTUState, SystemStatus } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface PtuStatePanelProps {
  ptuState: PTUState;
  systemStatus: SystemStatus;
}

export function PtuStatePanel({ ptuState, systemStatus }: PtuStatePanelProps) {
  const { t } = useTranslation();

  return (
    <DataPanel
      title={t('systemControl.ptuState', 'PTU State')}
      status={systemStatus.ptuOnline ? 'stable' : 'warning'}
    >
      <div className="space-y-2 text-sm">
        <DataRow
          label={t('waterfall.panAxis')}
          value={`${ptuState.panActual.toFixed(2)}° / ${ptuState.panTarget.toFixed(2)}°`}
        />
        <DataRow
          label={t('waterfall.tiltAxis')}
          value={`${ptuState.tiltActual.toFixed(2)}° / ${ptuState.tiltTarget.toFixed(2)}°`}
        />
        <DataRow
          label={t('systemControl.ptu.limits', 'Limits')}
          value={t('systemControl.nominal', 'Nominal')}
        />
        <DataRow
          label={t('systemControl.ptu.faults', 'Faults')}
          value={systemStatus.ptuOnline ? t('systemControl.none', 'None') : t('systemControl.offline', 'Offline')}
          warning={!systemStatus.ptuOnline}
        />
      </div>
    </DataPanel>
  );
}

