import { DataPanel, DataRow, DataGrid, DataCell } from '@/components/ui/DataPanel';
import type { KalmanState } from '@/types/tracking';

interface KalmanDisplayProps {
  state: KalmanState;
  className?: string;
}

export function KalmanDisplay({ state, className }: KalmanDisplayProps) {
  const timeSinceUpdate = Date.now() - state.lastUpdate;
  const isStale = timeSinceUpdate > 500;
  
  return (
    <DataPanel 
      title="KALMAN FILTER" 
      className={className}
      status={!state.enabled ? 'warning' : isStale ? 'error' : 'stable'}
      scrollable
    >
      <div className="space-y-3">
        <DataGrid columns={2}>
          <DataCell 
            label="Status" 
            value={state.enabled ? 'ENABLED' : 'DISABLED'} 
            variant={state.enabled ? 'success' : 'warning'}
            size="sm"
          />
          <DataCell 
            label="Mode" 
            value={state.predicting ? 'PREDICT' : 'UPDATE'} 
            variant={state.predicting ? 'warning' : 'default'}
            size="sm"
          />
        </DataGrid>

        <DataRow 
          label="Gating" 
          value={state.gatingActive ? 'ACTIVE' : 'INACTIVE'}
          warning={state.gatingActive}
        />
        
        <DataRow 
          label="Last Update" 
          value={timeSinceUpdate} 
          unit="ms"
          warning={timeSinceUpdate > 200}
          error={isStale}
        />

        {/* State Vector Visualization */}
        <div className="pt-2 border-t border-border/50">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">State Vector</div>
          <div className="grid grid-cols-2 gap-2 font-mono text-xs">
            <div className="bg-muted/30 p-2 rounded">
              <div className="text-[10px] text-muted-foreground">u</div>
              <div className="text-tactical-cyan">640.00</div>
            </div>
            <div className="bg-muted/30 p-2 rounded">
              <div className="text-[10px] text-muted-foreground">v</div>
              <div className="text-tactical-cyan">360.00</div>
            </div>
            <div className="bg-muted/30 p-2 rounded">
              <div className="text-[10px] text-muted-foreground">u̇</div>
              <div className="text-tactical-cyan">0.00</div>
            </div>
            <div className="bg-muted/30 p-2 rounded">
              <div className="text-[10px] text-muted-foreground">v̇</div>
              <div className="text-tactical-cyan">0.00</div>
            </div>
          </div>
        </div>
      </div>
    </DataPanel>
  );
}
