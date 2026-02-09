import { useState, useEffect } from 'react';
import { Header } from '@/components/layout/Header';
import { OperationalView } from '@/pages/OperationalView';
import { WaterfallView } from '@/pages/WaterfallView';
import { useSimulatedData } from '@/hooks/useSimulatedData';
import { useBalloonTracking } from '@/hooks/useBalloonTracking';
import { useOperationalTelemetry } from '@/hooks/useOperationalTelemetry';
import type { ScenarioId } from '@/types/tracking';
import { cn } from '@/lib/utils';
import { Monitor, Activity } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type ViewMode = 'operational' | 'waterfall';

const Index = () => {
  const { t } = useTranslation();
  const [activeScenario, setActiveScenario] = useState<ScenarioId>('D2_Z1');
  const [viewMode, setViewMode] = useState<ViewMode>('operational');
  const [currentTime, setCurrentTime] = useState(new Date());
  
  const { 
    balloons: simulatedBalloons, 
    ptuState, 
    kalmanState, 
    logs, 
    systemStatus 
  } = useSimulatedData(activeScenario);

  // Operational telemetry (laser, cooling, battery, environment, platform)
  const { telemetry, setOperationMode } = useOperationalTelemetry();

  // Live detections from backend YOLO tracking WebSocket
  const trackedBalloons = useBalloonTracking();
  const balloons = trackedBalloons;

  // Update time every second
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="h-screen w-screen flex flex-col bg-background overflow-hidden fixed inset-0">
      {/* Header */}
      <Header 
        activeScenario={activeScenario}
        systemStatus={systemStatus}
      />

      {/* View Mode Tabs */}
      <div className="flex items-center justify-between px-4 py-2 bg-card/50 border-b border-border flex-shrink-0">
        <div className="flex gap-2">
          <button
            onClick={() => setViewMode('operational')}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded text-sm font-medium transition-all',
              'border border-transparent',
              viewMode === 'operational'
                ? 'bg-primary/20 border-primary text-primary glow-green'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            )}
          >
            <Monitor className="w-4 h-4" />
            <span>{t('tabs.operational')}</span>
          </button>
          <button
            onClick={() => setViewMode('waterfall')}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded text-sm font-medium transition-all',
              'border border-transparent',
              viewMode === 'waterfall'
                ? 'bg-primary/20 border-primary text-primary glow-green'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
            )}
          >
            <Activity className="w-4 h-4" />
            <span>{t('tabs.waterfall')}</span>
          </button>
        </div>

        <div className="flex items-center gap-4">
          <div className="font-mono text-xs text-muted-foreground">
            {t('time.utc')}: {currentTime.toISOString().slice(11, 19)}
          </div>
          <div className="font-mono text-xs text-muted-foreground">
            {t('time.local')}: {currentTime.toLocaleTimeString('en-US', { hour12: false })}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden min-h-0">
        {viewMode === 'operational' ? (
          <OperationalView
            balloons={balloons}
            ptuState={ptuState}
            kalmanState={kalmanState}
            activeScenario={activeScenario}
            onScenarioChange={setActiveScenario}
            systemStatus={systemStatus}
            telemetry={telemetry}
            onOperationModeChange={setOperationMode}
          />
        ) : (
          <WaterfallView
            logs={logs}
            ptuState={ptuState}
            kalmanState={kalmanState}
          />
        )}
      </main>

      {/* CRT Scanline Effect */}
      <div className="crt-overlay pointer-events-none fixed inset-0" />
    </div>
  );
};

export default Index;
