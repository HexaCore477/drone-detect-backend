import { useState, useEffect } from 'react';
import { CameraView } from '@/components/tracking/CameraView';
import { PTUControl } from '@/components/tracking/PTUControl';
import { CameraZoomControl } from '@/components/tracking/CameraZoomControl';
import { OperationModeSelector } from '@/components/tracking/OperationModeSelector';
import { IndicatorPanels } from '@/components/tracking/IndicatorPanels';
import { DataPanel, DataGrid, DataCell, DataRow } from '@/components/ui/DataPanel';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { 
  DetectedBalloon, 
  PTUState, 
  KalmanState, 
  ScenarioId,
  SystemStatus,
  LaserStatus,
  WaterCoolingStatus,
  BatteryStatus,
  EnvironmentStatus,
  PlatformStatus,
  OperationMode,
} from '@/types/tracking';
import {
  DEFAULT_LASER_STATUS,
  DEFAULT_WATER_COOLING,
  DEFAULT_BATTERY,
  DEFAULT_ENVIRONMENT,
  DEFAULT_PLATFORM,
  DEFAULT_OPERATION_MODE,
} from '@/data/indicatorDefaults';
import { useTranslation } from 'react-i18next';
import { queryPtuPosition } from '@/api';

interface OperationalViewProps {
  balloons: DetectedBalloon[];
  ptuState: PTUState;
  kalmanState: KalmanState;
  activeScenario: ScenarioId;
  onScenarioChange: (id: ScenarioId) => void;
  systemStatus: SystemStatus;
  ptuPan?: number | null;
  ptuTilt?: number | null;
  laserStatus?: LaserStatus;
  waterCooling?: WaterCoolingStatus;
  battery?: BatteryStatus;
  environment?: EnvironmentStatus;
  platform?: PlatformStatus;
  operationMode?: OperationMode;
}

export function OperationalView({
  balloons,
  ptuState,
  kalmanState,
  activeScenario,
  onScenarioChange,
  systemStatus,
  ptuPan = null,
  ptuTilt = null,
  laserStatus = DEFAULT_LASER_STATUS,
  waterCooling = DEFAULT_WATER_COOLING,
  battery = DEFAULT_BATTERY,
  environment = DEFAULT_ENVIRONMENT,
  platform = DEFAULT_PLATFORM,
  operationMode: initialOperationMode = DEFAULT_OPERATION_MODE,
}: OperationalViewProps) {
  const { t } = useTranslation();
  const [operationMode, setOperationMode] = useState<OperationMode>(initialOperationMode);
  const [queriedPan, setQueriedPan] = useState<number | null>(null);
  const [queriedTilt, setQueriedTilt] = useState<number | null>(null);

  const effectivePtuState: PTUState = {
    ...ptuState,
    panActual: queriedPan ?? ptuPan ?? ptuState.panActual,
    tiltActual: queriedTilt ?? ptuTilt ?? ptuState.tiltActual,
  };

  const handleRefreshPtuPosition = async () => {
    try {
      const { pan, tilt } = await queryPtuPosition();
      setQueriedPan(pan);
      setQueriedTilt(tilt);
    } catch (e) {
      console.warn('PTU position query failed:', e);
    }
  };

  // Sync state with prop changes
  useEffect(() => {
    setOperationMode(initialOperationMode);
  }, [initialOperationMode]);

  // On page load, query PTU position and update azimuth/pitch
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { pan, tilt } = await queryPtuPosition();
        if (!cancelled) {
          setQueriedPan(pan);
          setQueriedTilt(tilt);
        }
      } catch (e) {
        if (!cancelled) console.warn('PTU position query on load failed:', e);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="h-full flex min-h-0">
      {/* Left Panel */}
      <div className="w-72 flex flex-col gap-3 p-3 border-r border-border bg-card/50 min-h-0">
        <ScrollArea className="flex-1 min-h-0">
          <div className="flex flex-col gap-3 pr-2">
            <CameraZoomControl />

            {/* Operation Mode */}
            <OperationModeSelector
              operationMode={operationMode}
              onModeChange={setOperationMode}
            />

            {/* Environment */}
            <DataPanel title={t('environment.title', 'Environment')} status="stable">
              <div className="space-y-1 text-sm">
                <DataRow label={t('environment.temp', 'Temperature')} value={environment.temperatureC.toFixed(1)} unit="°C" />
                <DataRow label={t('environment.pressure', 'Air pressure')} value={environment.airPressureHpa} unit="hPa" />
                <DataRow label={t('environment.humidity', 'Humidity')} value={environment.humidityPercent} unit="%" />
                <DataRow label={t('environment.windSpeed', 'Wind speed')} value={environment.windSpeedMs.toFixed(1)} unit="m/s" />
                <DataRow label={t('environment.windDir', 'Wind direction')} value={environment.windDirectionDeg} unit="°" />
                <DataRow label={t('environment.weather', 'Conditions')} value={environment.weatherConditions} />
              </div>
            </DataPanel>

            {/* Platform */}
            <DataPanel title={t('platform.title', 'Platform')} status="stable">
              <div className="space-y-1 text-sm">
                <DataRow label={t('platform.roll', 'Roll')} value={platform.attitude.roll.toFixed(1)} unit="°" />
                <DataRow label={t('platform.pitch', 'Pitch')} value={platform.attitude.pitch.toFixed(1)} unit="°" />
                <DataRow label={t('platform.yaw', 'Yaw')} value={platform.attitude.yaw.toFixed(1)} unit="°" />
                <DataRow label={t('platform.geo', 'Position')} value={platform.geoPosition} />
                <DataRow
                  label={t('platform.gps', 'GPS')}
                  value={`${platform.gpsCoordinates.lat.toFixed(6)}, ${platform.gpsCoordinates.lon.toFixed(6)}`}
                />
              </div>
            </DataPanel>
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
      <div className="w-80 flex flex-col gap-3 p-3 border-l border-border bg-card/50 min-h-0">
        <ScrollArea className="flex-1 min-h-0">
          <div className="flex flex-col gap-3 pr-2">
            <PTUControl ptuState={effectivePtuState} onRefreshPosition={handleRefreshPtuPosition} />
            <IndicatorPanels
              laserStatus={laserStatus}
              waterCooling={waterCooling}
              battery={battery}
            />
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}
