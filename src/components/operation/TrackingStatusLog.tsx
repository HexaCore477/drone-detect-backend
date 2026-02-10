import { DataPanel } from '@/components/ui/DataPanel';
import { LogViewer } from '@/components/tracking/LogViewer';
import type { LogEntry } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface TrackingStatusLogProps {
  logs: LogEntry[];
}

export function TrackingStatusLog({ logs }: TrackingStatusLogProps) {
  const { t } = useTranslation();

  return (
    <DataPanel title={t('waterfall.trackingStatus')} status="stable" className="flex-1">
      <LogViewer logs={logs} category="tracking" />
    </DataPanel>
  );
}

