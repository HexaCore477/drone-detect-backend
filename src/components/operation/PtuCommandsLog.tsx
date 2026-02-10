import { DataPanel } from '@/components/ui/DataPanel';
import { LogViewer } from '@/components/tracking/LogViewer';
import type { LogEntry } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface PtuCommandsLogProps {
  logs: LogEntry[];
}

export function PtuCommandsLog({ logs }: PtuCommandsLogProps) {
  const { t } = useTranslation();

  return (
    <DataPanel title={t('waterfall.ptuCommands')} status="stable" className="flex-1">
      <LogViewer logs={logs} category="ptu" />
    </DataPanel>
  );
}

