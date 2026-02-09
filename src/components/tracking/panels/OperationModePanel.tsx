import { DataPanel } from '@/components/ui/DataPanel';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import type { OperationMode } from '@/types/telemetry';

interface OperationModePanelProps {
  mode: OperationMode;
  onModeChange?: (mode: OperationMode) => void;
}

const modeLabels: Record<OperationMode, { short: string; full: string; color: string }> = {
  'human-in-the-loop': { 
    short: 'HITL', 
    full: 'Human-in-the-Loop',
    color: 'text-[hsl(var(--data-green))]'
  },
  'human-on-the-loop': { 
    short: 'HOTL', 
    full: 'Human-on-the-Loop',
    color: 'text-[hsl(var(--data-amber))]'
  },
  'human-out-of-the-loop': { 
    short: 'HOOL', 
    full: 'Human-out-of-the-Loop',
    color: 'text-[hsl(var(--data-red))]'
  },
};

export function OperationModePanel({ mode, onModeChange }: OperationModePanelProps) {
  const { t } = useTranslation();
  const modeInfo = modeLabels[mode];
  
  return (
    <DataPanel title={t('opMode.title', 'Operation Mode')}>
      <div className="space-y-2">
        <div className="text-center py-2">
          <span className={cn('font-mono text-2xl font-bold', modeInfo.color)}>
            {modeInfo.short}
          </span>
          <p className="text-xs text-muted-foreground mt-1">{modeInfo.full}</p>
        </div>
        {onModeChange && (
          <div className="flex gap-1">
            {(Object.keys(modeLabels) as OperationMode[]).map((m) => (
              <button
                key={m}
                onClick={() => onModeChange(m)}
                className={cn(
                  'flex-1 px-2 py-1 text-[10px] font-bold rounded border transition-colors',
                  m === mode 
                    ? 'bg-primary/20 border-primary text-primary' 
                    : 'border-border text-muted-foreground hover:border-primary/50'
                )}
              >
                {modeLabels[m].short}
              </button>
            ))}
          </div>
        )}
      </div>
    </DataPanel>
  );
}
