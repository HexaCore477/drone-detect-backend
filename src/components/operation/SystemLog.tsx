import { DataPanel } from '@/components/ui/DataPanel';
import { LogViewer } from '@/components/tracking/LogViewer';
import type { LogEntry } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface SystemLogProps {
  logs: LogEntry[];
}

export function SystemLog({ logs }: SystemLogProps) {
  const { t } = useTranslation();

  return (
    <DataPanel title={t('waterfall.systemLog')} status="stable" className="col-span-2">
      <LogViewer logs={logs} category="system" />
    </DataPanel>
  );
}

