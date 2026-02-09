import { CameraView } from '@/components/tracking/CameraView';
import { KalmanDisplay } from '@/components/tracking/KalmanDisplay';
import { PTUControl } from '@/components/tracking/PTUControl';
import { ScenarioSelector } from '@/components/tracking/ScenarioSelector';
import { DataPanel, DataRow, DataGrid, DataCell } from '@/components/ui/DataPanel';
import { ScrollArea } from '@/components/ui/scroll-area';

// New telemetry panels
import { DroneDataPanel } from '@/components/tracking/panels/DroneDataPanel';
import { LaserStatusPanel } from '@/components/tracking/panels/LaserStatusPanel';
import { CoolingStatusPanel } from '@/components/tracking/panels/CoolingStatusPanel';
import { BatteryStatusPanel } from '@/components/tracking/panels/BatteryStatusPanel';
import { OperationModePanel } from '@/components/tracking/panels/OperationModePanel';
import { EnvironmentPanel } from '@/components/tracking/panels/EnvironmentPanel';
import { PlatformStatusPanel } from '@/components/tracking/panels/PlatformStatusPanel';

import type { 
  DetectedBalloon, 
  PTUState, 
  KalmanState, 
  ScenarioId,
  SystemStatus 
} from '@/types/tracking';
import type { OperationalTelemetry, OperationMode } from '@/types/telemetry';
import { SCENARIOS } from '@/data/scenarios';
import { useTranslation } from 'react-i18next';

interface OperationalViewProps {
  balloons: DetectedBalloon[];
  ptuState: PTUState;
  kalmanState: KalmanState;
  activeScenario: ScenarioId;
  onScenarioChange: (id: ScenarioId) => void;
  systemStatus: SystemStatus;
  telemetry: OperationalTelemetry;
  onOperationModeChange?: (mode: OperationMode) => void;
}

export function OperationalView({
  balloons,
  ptuState,
  kalmanState,
  activeScenario,
  onScenarioChange,
  systemStatus,
  telemetry,
  onOperationModeChange,
}: OperationalViewProps) {
  const { t } = useTranslation();
  const scenario = SCENARIOS[activeScenario];
  
  return (
    <div className="h-full flex min-h-0">
      {/* Left Panel - System Status */}
      <div className="w-64 flex flex-col gap-2 p-2 border-r border-border bg-card/50 min-h-0">
        <ScrollArea className="flex-1 min-h-0">
          <div className="flex flex-col gap-2 pr-2">
            <ScenarioSelector 
              activeScenario={activeScenario} 
              onSelect={onScenarioChange} 
            />
            
            <OperationModePanel 
              mode={telemetry.operationMode}
              onModeChange={onOperationModeChange}
            />
            
            <DroneDataPanel data={telemetry.drone} />
            
            <KalmanDisplay state={kalmanState} />
            
            <DataPanel title={t('tracking.latency', 'System Latency')}>
              <DataGrid columns={2}>
                <DataCell 
                  label={t('tracking.current', 'Current')} 
                  value={systemStatus.latencyMs} 
                  unit="ms" 
                  variant={systemStatus.latencyMs > 100 ? 'warning' : 'success'}
                  size="sm"
                />
                <DataCell 
                  label={t('tracking.comp', 'Comp')} 
                  value="200" 
                  unit="ms" 
                  size="sm"
                />
              </DataGrid>
            </DataPanel>
          </div>
        </ScrollArea>
      </div>

      {/* Center: Camera View */}
      <div className="flex-1 flex flex-col p-2 gap-2 min-h-0">
        {/* Camera View - Takes remaining space */}
        <div className="flex-1 relative min-h-0 flex items-center justify-center overflow-hidden">
          <div className="w-full h-full" style={{ maxWidth: '100%', maxHeight: '100%', aspectRatio: '16/9' }}>
            <CameraView 
              balloons={balloons}
              showCrosshair={true}
              laserStatus={telemetry.laser}
            />
          </div>
          
          {/* Top Left Overlay Info */}
          <div className="absolute top-2 left-2 flex flex-col gap-1.5 z-10">
            <div className="bg-black/80 backdrop-blur-sm px-2 py-1 rounded border border-border/50">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${
                  systemStatus.trackingActive ? 'bg-[hsl(var(--status-stable))] shadow-[0_0_8px_hsl(var(--status-stable))]' : 'bg-[hsl(var(--status-error))]'
                }`} />
                <span className="font-mono text-[10px] text-primary uppercase">
                  {systemStatus.trackingActive ? t('camera.trackingActive') : t('camera.trackingIdle')}
                </span>
              </div>
            </div>
            
            <div className="bg-black/80 backdrop-blur-sm px-2 py-1 rounded border border-border/50">
              <div className="font-mono text-[10px]">
                <span className="text-muted-foreground">{t('camera.mode')}: </span>
                <span className="text-[hsl(var(--data-cyan))]">{t('camera.auto')}</span>
              </div>
            </div>
          </div>

          {/* Bottom Left Overlay */}
          <div className="absolute bottom-2 left-2 z-10">
            <div className="bg-black/80 backdrop-blur-sm px-2 py-1 rounded border border-border/50">
              <div className="font-mono text-[10px] text-muted-foreground">
                {t('scenario.scene')}: <span className="text-primary">{activeScenario}</span>
                <span className="mx-1.5">|</span>
                {t('camera.kf')}: <span className={kalmanState.enabled ? 'text-[hsl(var(--status-stable))]' : 'text-[hsl(var(--status-warning))]'}>
                  {kalmanState.enabled ? t('camera.on') : t('camera.off')}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Stats Bar - Compact */}
        <div className="flex gap-2 flex-shrink-0">
          <DataPanel title={t('tracking.metricsTitle')} className="flex-1">
            <DataGrid columns={4}>
              <DataCell label={t('tracking.centerError')} value="3.2" unit="px" variant="default" size="sm" />
              <DataCell label={t('tracking.trackQuality')} value="98.5" unit="%" variant="success" size="sm" />
              <DataCell label={t('tracking.updateRate')} value="30" unit="fps" variant="success" size="sm" />
              <DataCell label={t('tracking.procTime')} value="12.5" unit="ms" variant="default" size="sm" />
            </DataGrid>
          </DataPanel>
          
          <DataPanel title="PTU Angles" className="w-48">
            <DataGrid columns={2}>
              <DataCell label="Pan" value={ptuState.panActual.toFixed(1)} unit="°" size="sm" />
              <DataCell label="Tilt" value={ptuState.tiltActual.toFixed(1)} unit="°" size="sm" />
            </DataGrid>
          </DataPanel>
        </div>
      </div>

      {/* Right Panel - Hardware & Environment */}
      <div className="w-64 flex flex-col gap-2 p-2 border-l border-border bg-card/50 min-h-0">
        <ScrollArea className="flex-1 min-h-0">
          <div className="flex flex-col gap-2 pr-2">
            <LaserStatusPanel status={telemetry.laser} />
            
            <CoolingStatusPanel status={telemetry.cooling} />
            
            <BatteryStatusPanel status={telemetry.battery} />
            
            <EnvironmentPanel status={telemetry.environment} />
            
            <PlatformStatusPanel status={telemetry.platform} />
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
