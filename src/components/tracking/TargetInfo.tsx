import { DataPanel, DataRow, DataGrid, DataCell } from '@/components/ui/DataPanel';
import type { DetectedBalloon, BalloonSize } from '@/types/tracking';
import { cn } from '@/lib/utils';

interface TargetInfoProps {
  balloons: DetectedBalloon[];
  activeTarget: DetectedBalloon | null;
  className?: string;
}

const sizeLabels: Record<BalloonSize, string> = {
  large: 'LRG',
  medium: 'MED',
  small: 'SML',
};

const sizePriority: Record<BalloonSize, number> = {
  large: 1,
  medium: 2,
  small: 3,
};

export function TargetInfo({ balloons, activeTarget, className }: TargetInfoProps) {
  const redBalloons = balloons.filter(b => b.color === 'red');
  const sortedRed = [...redBalloons].sort((a, b) => sizePriority[a.size] - sizePriority[b.size]);
  
  return (
    <DataPanel 
      title="TARGET ACQUISITION" 
      className={className}
      status={activeTarget ? 'stable' : redBalloons.length > 0 ? 'warning' : 'error'}
      scrollable
    >
      <div className="space-y-3">
        {/* Detection Summary */}
        <DataGrid columns={2}>
          <DataCell 
            label="Total Detected" 
            value={balloons.length} 
            variant="default"
            size="lg"
          />
          <DataCell 
            label="Red (Hostile)" 
            value={redBalloons.length} 
            variant={redBalloons.length > 0 ? 'error' : 'default'}
            size="lg"
          />
        </DataGrid>

        {/* Active Target */}
        {activeTarget && (
          <div className="p-2 bg-destructive/20 border border-destructive/50 rounded">
            <div className="text-[10px] text-destructive uppercase tracking-wider mb-1">Active Target</div>
            <div className="flex items-center justify-between">
              <span className="font-mono text-sm font-bold text-destructive glow-red">
                {activeTarget.color.toUpperCase()}-{sizeLabels[activeTarget.size]}
              </span>
              <span className="font-mono text-xs text-tactical-cyan">
                ({activeTarget.centerX.toFixed(0)}, {activeTarget.centerY.toFixed(0)})
              </span>
            </div>
          </div>
        )}

        {/* Target Queue */}
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">Target Priority Queue</div>
          <div className="space-y-1">
            {sortedRed.length === 0 ? (
              <div className="text-muted-foreground text-xs text-center py-2">No hostile targets</div>
            ) : (
              sortedRed.map((balloon, index) => (
                <div 
                  key={balloon.id}
                  className={cn(
                    'flex items-center justify-between px-2 py-1 rounded text-xs font-mono',
                    balloon.isTarget 
                      ? 'bg-destructive/30 border border-destructive/50' 
                      : 'bg-muted/30'
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">#{index + 1}</span>
                    <span className={cn(
                      balloon.isTarget ? 'text-destructive font-bold' : 'text-foreground'
                    )}>
                      {sizeLabels[balloon.size]}
                    </span>
                  </div>
                  <span className="text-tactical-cyan">
                    {balloon.centerX.toFixed(0)},{balloon.centerY.toFixed(0)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </DataPanel>
  );
}
