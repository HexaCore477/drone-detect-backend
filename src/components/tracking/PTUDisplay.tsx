import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { PTUState } from '@/types/tracking';

interface PTUDisplayProps {
  state: PTUState;
  className?: string;
}

export function PTUDisplay({ state, className }: PTUDisplayProps) {
  return (
    <DataPanel 
      title="PTU STATUS" 
      className={className}
      status="stable"
      scrollable
    >
      <div className="space-y-3">
        {/* Azimuth (Pan) Section */}
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Azimuth</div>
          <DataRow 
            label="Actual" 
            value={state.panActual.toFixed(2)} 
            unit="°"
            highlight
          />
        </div>

        {/* Pitch (Tilt) Section */}
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Pitch</div>
          <DataRow 
            label="Actual" 
            value={state.tiltActual.toFixed(2)} 
            unit="°"
            highlight
          />
        </div>

        {/* Visual Gauge */}
        {/* <div className="pt-2 border-t border-border/50">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="text-[10px] text-muted-foreground mb-1">AZIMUTH</div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div 
                  className="h-full bg-primary transition-all duration-150"
                  style={{ width: `${Math.min(100, Math.max(0, 50 + (state.panActual / 180) * 50))}%` }}
                />
              </div>
            </div>
            <div className="flex-1">
              <div className="text-[10px] text-muted-foreground mb-1">PITCH</div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div 
                  className="h-full bg-primary transition-all duration-150"
                  style={{ width: `${Math.min(100, Math.max(0, 50 + (state.tiltActual / 90) * 50))}%` }}
                />
              </div>
            </div>
          </div>
        </div> */}
      </div>
    </DataPanel>
  );
}
