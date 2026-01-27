import { CameraView } from '@/components/tracking/CameraView';
import { KalmanDisplay } from '@/components/tracking/KalmanDisplay';
import { PTUControl } from '@/components/tracking/PTUControl';
import { ScenarioSelector } from '@/components/tracking/ScenarioSelector';
import { DataPanel, DataRow, DataGrid, DataCell } from '@/components/ui/DataPanel';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { 
  DetectedBalloon, 
  PTUState, 
  KalmanState, 
  ScenarioId,
  SystemStatus 
} from '@/types/tracking';
import { SCENARIOS } from '@/data/scenarios';

interface OperationalViewProps {
  balloons: DetectedBalloon[];
  ptuState: PTUState;
  kalmanState: KalmanState;
  activeScenario: ScenarioId;
  onScenarioChange: (id: ScenarioId) => void;
  systemStatus: SystemStatus;
}

export function OperationalView({
  balloons,
  ptuState,
  kalmanState,
  activeScenario,
  onScenarioChange,
  systemStatus,
}: OperationalViewProps) {
  const scenario = SCENARIOS[activeScenario];
  
  return (
    <div className="h-full flex min-h-0">
      {/* Left Panel */}
      <div className="w-72 flex flex-col gap-3 p-3 border-r border-border bg-card/50 min-h-0">
        <div className="flex-shrink-0">
          <ScenarioSelector 
            activeScenario={activeScenario} 
            onSelect={onScenarioChange} 
          />
        </div>
        
        <ScrollArea className="flex-1 min-h-0">
          <div className="flex flex-col gap-3 pr-2">
            <DataPanel title="SCENARIO CONFIG" status="stable">
              <div className="space-y-1 text-sm">
                <DataRow label="Distance" value={scenario.distance} unit="m" />
                <DataRow label="Zoom" value={`${scenario.zoom}×`} />
                <DataRow label="Deadband" value="5" unit="px" />
                <DataRow label="Max Rate" value="10.0" unit="°/s" />
                <DataRow label="Max Step" value="2.0" unit="°" />
                <DataRow label="Latency" value="200" unit="ms" />
              </div>
            </DataPanel>

            <PTUDisplay state={ptuState} />
          </div>
        </ScrollArea>
      </div>

      {/* Center: Camera View */}
      <div className="flex-1 flex flex-col p-3 gap-3 min-h-0">
        {/* Camera View - Takes remaining space */}
        <div className="flex-1 relative min-h-0 flex items-center justify-center overflow-hidden">
          <div className="w-full h-full" style={{ maxWidth: '100%', maxHeight: '100%', aspectRatio: '16/9' }}>
            <CameraView 
              balloons={balloons}
              centerX={640}
              centerY={360}
              showGrid={true}
              showCrosshair={true}
            />
          </div>
          
          {/* Overlay Info */}
          <div className="absolute top-3 left-3 flex flex-col gap-2 z-10">
            <div className="bg-black/70 backdrop-blur-sm px-3 py-1.5 rounded border border-border/50">
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${
                  systemStatus.trackingActive ? 'bg-tactical-green shadow-[0_0_8px_hsl(var(--status-stable))]' : 'bg-tactical-red'
                }`} />
                <span className="font-mono text-xs text-primary uppercase">
                  {systemStatus.trackingActive ? 'Tracking Active' : 'Tracking Idle'}
                </span>
              </div>
            </div>
            
            <div className="bg-black/70 backdrop-blur-sm px-3 py-1.5 rounded border border-border/50">
              <div className="font-mono text-xs">
                <span className="text-muted-foreground">MODE: </span>
                <span className="text-tactical-cyan">AUTO</span>
              </div>
            </div>
          </div>

          {/* Bottom Left Overlay */}
          <div className="absolute bottom-3 left-3 z-10">
            <div className="bg-black/70 backdrop-blur-sm px-3 py-1.5 rounded border border-border/50">
              <div className="font-mono text-[10px] text-muted-foreground">
                SCENE: <span className="text-primary">{activeScenario}</span>
                <span className="mx-2">|</span>
                KF: <span className={kalmanState.enabled ? 'text-tactical-green' : 'text-tactical-amber'}>
                  {kalmanState.enabled ? 'ON' : 'OFF'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Stats Bar - Fixed height */}
        <div className="flex gap-3 flex-shrink-0 h-auto">
          <DataPanel title="TRACKING METRICS" className="flex-1">
            <DataGrid columns={4}>
              <DataCell label="Frame Rate" value="30" unit="fps" variant="success" />
              <DataCell label="Proc Time" value="12.5" unit="ms" variant="default" />
              <DataCell label="Pixel Error" value="3.2" unit="px" variant="default" />
              <DataCell label="Stability" value="98.5" unit="%" variant="success" />
            </DataGrid>
          </DataPanel>
          
          <DataPanel title="CONTROL LIMITS" className="flex-1">
            <DataGrid columns={4}>
              <DataCell label="Pan Limit" value="±180" unit="°" />
              <DataCell label="Tilt Limit" value="±45" unit="°" />
              <DataCell label="Vel Limit" value="10.0" unit="°/s" />
              <DataCell label="Accel" value="5.0" unit="°/s²" />
            </DataGrid>
          </DataPanel>
        </div>
      </div>

      {/* Right Panel */}
      <div className="w-72 flex flex-col gap-3 p-3 border-l border-border bg-card/50 min-h-0">
        <ScrollArea className="flex-1 min-h-0">
          <div className="flex flex-col gap-3 pr-2">
            <TargetInfo 
              balloons={balloons} 
              activeTarget={activeTarget}
            />
            
            <KalmanDisplay state={kalmanState} />
            
            <DataPanel title="EMITTER STATUS" status="stable">
              <div className="space-y-1 text-sm">
                <DataRow label="Pan Offset" value="0.00" unit="°" />
                <DataRow label="Tilt Offset" value="0.00" unit="°" />
                <DataRow label="Focus" value="AUTO" />
                <DataRow label="Power" value="100" unit="%" />
              </div>
            </DataPanel>
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
