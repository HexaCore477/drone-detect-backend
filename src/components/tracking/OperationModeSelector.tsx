import { cn } from '@/lib/utils';
import type { OperationMode } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface OperationModeSelectorProps {
  operationMode: OperationMode;
  onModeChange: (mode: OperationMode) => void;
  className?: string;
}

const getModeAbbreviation = (mode: OperationMode, t: (key: string) => string): string => {
  const abbreviations: Record<OperationMode, string> = {
    'human-in-the-loop': t('mode.hitl'),
    'human-on-the-loop': t('mode.hotl'),
    'human-out-of-the-loop': t('mode.hool'),
  };
  return abbreviations[mode];
};

const getModeLabel = (mode: OperationMode, t: (key: string) => string): string => {
  const labels: Record<OperationMode, string> = {
    'human-in-the-loop': t('mode.humanInTheLoop'),
    'human-on-the-loop': t('mode.humanOnTheLoop'),
    'human-out-of-the-loop': t('mode.humanOutOfTheLoop'),
  };
  return labels[mode];
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
            {getModeAbbreviation(operationMode, t)}
          </div>
          {/* Full Description */}
          <div className="text-sm text-muted-foreground font-sans">
            {getModeLabel(operationMode, t)}
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
                {getModeAbbreviation(mode, t)}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
