import { useState, useEffect } from 'react';
import { Header } from '@/components/layout/Header';
import { OperationalView } from '@/pages/OperationalView';
import { useSimulatedData } from '@/hooks/useSimulatedData';
import type { ScenarioId } from '@/types/tracking';

const Index = () => {
  const [activeScenario, setActiveScenario] = useState<ScenarioId>('D2_Z1');
  const [currentTime, setCurrentTime] = useState(new Date());
  
  const { 
    balloons, 
    ptuState, 
    kalmanState, 
    logs, 
    systemStatus 
  } = useSimulatedData(activeScenario);

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

      {/* Time Display Bar */}
      <div className="flex items-center justify-end px-4 py-2 bg-card/50 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-4">
          <div className="font-mono text-xs text-muted-foreground">
            UTC: {currentTime.toISOString().slice(11, 19)}
          </div>
          <div className="font-mono text-xs text-muted-foreground">
            LOCAL: {currentTime.toLocaleTimeString('en-US', { hour12: false })}
          </div>
        </div>
      </div>

      {/* Main Content - Always show Operational View in full screen */}
      <main className="flex-1 overflow-hidden min-h-0">
        <OperationalView
          balloons={balloons}
          ptuState={ptuState}
          kalmanState={kalmanState}
          activeScenario={activeScenario}
          onScenarioChange={setActiveScenario}
          systemStatus={systemStatus}
        />
      </main>

      {/* CRT Scanline Effect */}
      <div className="crt-overlay pointer-events-none fixed inset-0" />
    </div>
  );
};

export default Index;
