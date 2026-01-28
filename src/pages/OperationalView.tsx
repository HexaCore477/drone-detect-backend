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
import { useTranslation } from 'react-i18next';

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
  const { t } = useTranslation();
  const scenario = SCENARIOS[activeScenario];
  
  return (
    <div className="h-full flex min-h-0">
      {/* Left Panel */}
      <div className="w-72 flex flex-col gap-3 p-3 border-r border-border bg-card/50 min-h-0">
        <ScrollArea className="flex-1 min-h-0">
          <div className="flex flex-col gap-3 pr-2">
            <ScenarioSelector 
              activeScenario={activeScenario} 
              onSelect={onScenarioChange} 
            />
            <DataPanel title={t('scenario.config')} status="stable" scrollable>
              <div className="space-y-1 text-sm">
                <DataRow label={t('scenario.distance')} value={scenario.distance} unit="m" />
                <DataRow label={t('scenario.zoom')} value={`${scenario.zoom}×`} />
                <DataRow label={t('scenario.deadband')} value="5" unit="px" />
                <DataRow label={t('scenario.maxRate')} value="10.0" unit="°/s" />
                <DataRow label={t('scenario.maxStep')} value="2.0" unit="°" />
                <DataRow label={t('scenario.latency')} value="200" unit="ms" />
              </div>
            </DataPanel>

            <KalmanDisplay state={kalmanState} />
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
                  {systemStatus.trackingActive ? t('camera.trackingActive') : t('camera.trackingIdle')}
                </span>
              </div>
            </div>
            
            <div className="bg-black/70 backdrop-blur-sm px-3 py-1.5 rounded border border-border/50">
              <div className="font-mono text-xs">
                <span className="text-muted-foreground">{t('camera.mode')}: </span>
                <span className="text-tactical-cyan">{t('camera.auto')}</span>
              </div>
            </div>
          </div>

          {/* Bottom Left Overlay */}
          <div className="absolute bottom-3 left-3 z-10">
            <div className="bg-black/70 backdrop-blur-sm px-3 py-1.5 rounded border border-border/50">
              <div className="font-mono text-[10px] text-muted-foreground">
                {t('scenario.scene')}: <span className="text-primary">{activeScenario}</span>
                <span className="mx-2">|</span>
                {t('camera.kf')}: <span className={kalmanState.enabled ? 'text-tactical-green' : 'text-tactical-amber'}>
                  {kalmanState.enabled ? t('camera.on') : t('camera.off')}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Stats Bar - Fixed height */}
        <div className="flex gap-3 flex-shrink-0 h-auto">
          <DataPanel title={t('tracking.metricsTitle')} className="flex-1">
            <DataGrid columns={4}>
              <DataCell label={t('tracking.centerError')} value="3.2" unit="px" variant="default" />
              <DataCell label={t('tracking.trackQuality')} value="98.5" unit="%" variant="success" />
              <DataCell label={t('tracking.updateRate')} value="30" unit="fps" variant="success" />
              <DataCell label={t('tracking.procTime')} value="12.5" unit="ms" variant="default" />
            </DataGrid>
          </DataPanel>
          
          <DataPanel title={t('tracking.limitsTitle')} className="flex-1">
            <DataGrid columns={4}>
              <DataCell label={t('tracking.maxVelocity')} value="10.0" unit="°/s" />
              <DataCell label={t('tracking.deadband')} value="5" unit="px" />
              <DataCell label={t('tracking.latencyComp')} value="200" unit="ms" />
              <DataCell label={t('tracking.accel')} value="5.0" unit="°/s²" />
            </DataGrid>
          </DataPanel>
        </div>
      </div>

      {/* Right Panel */}
      <div className="w-72 flex flex-col gap-3 p-3 border-l border-border bg-card/50 min-h-0">
        <ScrollArea className="flex-1 min-h-0">
          <div className="flex flex-col gap-3 pr-2">
            <PTUControl ptuState={ptuState} />
            
            <DataPanel title={t('emitter.title')} status="stable">
              <div className="space-y-1 text-sm">
                <DataRow label={t('emitter.panOffset')} value="0.00" unit="°" />
                <DataRow label={t('emitter.tiltOffset')} value="0.00" unit="°" />
                <DataRow label={t('emitter.focus')} value={t('camera.auto')} />
                <DataRow label={t('emitter.power')} value="100" unit="%" />
              </div>
            </DataPanel>
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
