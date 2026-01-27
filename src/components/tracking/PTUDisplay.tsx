import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { PTUState } from '@/types/tracking';

interface PTUDisplayProps {
  state: PTUState;
  className?: string;
}

export function PTUDisplay({ state, className }: PTUDisplayProps) {
  const panError = Math.abs(state.panTarget - state.panActual);
  const tiltError = Math.abs(state.tiltTarget - state.tiltActual);
  
  const panStatus = panError > 2 ? 'warning' : panError > 5 ? 'error' : 'stable';
  const tiltStatus = tiltError > 2 ? 'warning' : tiltError > 5 ? 'error' : 'stable';
  
  return (
    <DataPanel 
      title="PTU STATUS" 
      className={className}
      status={panError > 5 || tiltError > 5 ? 'error' : panError > 2 || tiltError > 2 ? 'warning' : 'stable'}
    >
      <div className="space-y-3">
        {/* Pan Section */}
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Pan Axis</div>
          <DataRow 
            label="Target" 
            value={state.panTarget.toFixed(2)} 
            unit="°" 
            warning={panStatus === 'warning'}
            error={panStatus === 'error'}
          />
          <DataRow 
            label="Actual" 
            value={state.panActual.toFixed(2)} 
            unit="°"
          />
          <DataRow 
            label="Error" 
            value={panError.toFixed(2)} 
            unit="°"
            warning={panStatus === 'warning'}
            error={panStatus === 'error'}
          />
        </div>

        {/* Tilt Section */}
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">Tilt Axis</div>
          <DataRow 
            label="Target" 
            value={state.tiltTarget.toFixed(2)} 
            unit="°"
            warning={tiltStatus === 'warning'}
            error={tiltStatus === 'error'}
          />
          <DataRow 
            label="Actual" 
            value={state.tiltActual.toFixed(2)} 
            unit="°"
          />
          <DataRow 
            label="Error" 
            value={tiltError.toFixed(2)} 
            unit="°"
            warning={tiltStatus === 'warning'}
            error={tiltStatus === 'error'}
          />
        </div>

        {/* Visual Gauge */}
        <div className="pt-2 border-t border-border/50">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="text-[10px] text-muted-foreground mb-1">PAN</div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div 
                  className="h-full bg-primary transition-all duration-150"
                  style={{ width: `${Math.min(100, Math.max(0, 50 + (state.panActual / 180) * 50))}%` }}
                />
              </div>
            </div>
            <div className="flex-1">
              <div className="text-[10px] text-muted-foreground mb-1">TILT</div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div 
                  className="h-full bg-primary transition-all duration-150"
                  style={{ width: `${Math.min(100, Math.max(0, 50 + (state.tiltActual / 90) * 50))}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </DataPanel>
  );
}
