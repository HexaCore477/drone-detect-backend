import { DataPanel } from '@/components/ui/DataPanel';
import { LogViewer } from '@/components/tracking/LogViewer';
import type { LogEntry } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface KalmanFilterLogProps {
  logs: LogEntry[];
}

export function KalmanFilterLog({ logs }: KalmanFilterLogProps) {
  const { t } = useTranslation();

  return (
    <DataPanel title={t('waterfall.kalmanFilterLog')} status="stable" className="flex-1">
      <LogViewer logs={logs} category="kalman" />
    </DataPanel>
  );
}

