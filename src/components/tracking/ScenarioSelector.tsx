import { cn } from '@/lib/utils';
import { SCENARIOS, SCENARIO_ORDER } from '@/data/scenarios';
import type { ScenarioId } from '@/types/tracking';

interface ScenarioSelectorProps {
  activeScenario: ScenarioId;
  onSelect: (id: ScenarioId) => void;
  className?: string;
}

export function ScenarioSelector({ activeScenario, onSelect, className }: ScenarioSelectorProps) {
  return (
    <div className={cn('panel', className)}>
      <div className="panel-header">
        <span className="text-primary glow-green">ACTIVE SCENARIO</span>
      </div>
      <div className="p-2 space-y-1">
        {SCENARIO_ORDER.map((id) => {
          const scenario = SCENARIOS[id];
          const isActive = id === activeScenario;
          
          return (
            <button
              key={id}
              onClick={() => onSelect(id)}
              className={cn(
                'w-full flex items-center justify-between px-3 py-2 rounded text-left transition-all',
                'border border-transparent',
                isActive 
                  ? 'bg-primary/20 border-primary text-primary glow-green' 
                  : 'hover:bg-muted/50 text-muted-foreground hover:text-foreground'
              )}
            >
              <span className="font-mono text-sm font-semibold">{id}</span>
              <span className="text-xs">{scenario.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

interface ScenarioInfoProps {
  scenarioId: ScenarioId;
  className?: string;
}

export function ScenarioInfo({ scenarioId, className }: ScenarioInfoProps) {
  const scenario = SCENARIOS[scenarioId];
  
  return (
    <div className={cn('flex items-center gap-4 font-mono', className)}>
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground text-xs">SCENE:</span>
        <span className="text-primary font-bold glow-green">{scenarioId}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground text-xs">DIST:</span>
        <span className="text-tactical-cyan">{scenario.distance}m</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-muted-foreground text-xs">ZOOM:</span>
        <span className="text-tactical-cyan">{scenario.zoom}×</span>
      </div>
    </div>
  );
}
