import { cn } from '@/lib/utils';
import type { OperationMode } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface OperationModeSelectorProps {
  operationMode: OperationMode;
  onModeChange: (mode: OperationMode) => void;
  className?: string;
}

const modeAbbreviation: Record<OperationMode, string> = {
  'human-in-the-loop': 'HITL',
  'human-on-the-loop': 'HOTL',
  'human-out-of-the-loop': 'HOOL',
};

const modeLabel: Record<OperationMode, string> = {
  'human-in-the-loop': 'Human-in-the-Loop',
  'human-on-the-loop': 'Human-on-the-Loop',
  'human-out-of-the-loop': 'Human-out-of-the-Loop',
};

const modeOptions: OperationMode[] = [
  'human-in-the-loop',
  'human-on-the-loop',
  'human-out-of-the-loop',
];

export function OperationModeSelector({
  operationMode,
  onModeChange,
  className,
}: OperationModeSelectorProps) {
  const { t } = useTranslation();

  return (
    <div className={cn('panel flex flex-col overflow-hidden', className)}>
      {/* Header */}
      <div className="panel-header flex-shrink-0">
        <span className="text-primary glow-green font-mono uppercase">
          {t('mode.title', 'OPERATION MODE')}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 flex flex-col p-4">
        {/* Current Mode Display */}
        <div className="flex flex-col items-center justify-center mb-6 space-y-2">
          {/* Large Abbreviation */}
          <div className="font-mono text-4xl font-bold text-primary glow-green">
            {modeAbbreviation[operationMode]}
          </div>
          {/* Full Description */}
          <div className="text-sm text-muted-foreground font-sans">
            {modeLabel[operationMode]}
          </div>
        </div>

        {/* Mode Selection Buttons */}
        <div className="flex gap-2 mt-auto">
          {modeOptions.map((mode) => {
            const isActive = mode === operationMode;
            return (
              <button
                key={mode}
                onClick={() => onModeChange(mode)}
                className={cn(
                  'flex-1 px-3 py-2 rounded border transition-all',
                  'font-mono text-xs uppercase font-semibold',
                  isActive
                    ? 'bg-primary text-primary-foreground border-primary glow-green'
                    : 'bg-transparent text-primary border-primary hover:bg-primary/10'
                )}
              >
                {modeAbbreviation[mode]}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
