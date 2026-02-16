import { DataPanel } from '@/components/ui/DataPanel';
import { LogViewer } from '@/components/tracking/LogViewer';
import type { LogEntry } from '@/types/tracking';
import type { PtuCommand } from '@/hooks/usePtuCommands';
import { useTranslation } from 'react-i18next';

function ptuCommandsToLogEntries(commands: PtuCommand[]): LogEntry[] {
  return commands.map((c, i) => ({
    id: `ptu-cmd-${c.timestamp}-${i}`,
    timestamp: new Date(c.timestamp),
    level: 'success' as const,
    category: 'ptu' as const,
    message: c.command,
  }));
}

interface PtuCommandsLogProps {
  logs: LogEntry[];
  ptuCommands?: PtuCommand[];
}

export function PtuCommandsLog({ logs, ptuCommands = [] }: PtuCommandsLogProps) {
  const { t } = useTranslation();

  const ptuEntries = ptuCommandsToLogEntries(ptuCommands);
  const allLogs = [
    ...logs.filter((l) => l.category === 'ptu'),
    ...ptuEntries,
  ].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

  const status = ptuCommands.length > 0 ? 'stable' : undefined;

  return (
    <DataPanel title={t('waterfall.ptuCommands')} status={status} className="flex-1">
      <LogViewer logs={allLogs} category="ptu" />
    </DataPanel>
  );
}

