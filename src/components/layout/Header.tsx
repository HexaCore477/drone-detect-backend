import { cn } from '@/lib/utils';
import { StatusIndicator } from '@/components/ui/StatusIndicator';
import { ScenarioInfo } from '@/components/tracking/ScenarioSelector';
import type { ScenarioId, SystemStatus } from '@/types/tracking';
import { Activity, Radio, Video, Crosshair } from 'lucide-react';

interface HeaderProps {
  activeScenario: ScenarioId;
  systemStatus: SystemStatus;
  className?: string;
}

export function Header({ activeScenario, systemStatus, className }: HeaderProps) {
  return (
    <header className={cn(
      'flex items-center justify-between px-4 py-2 bg-card border-b border-border',
      className
    )}>
      {/* Left: System Title */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Crosshair className="w-6 h-6 text-primary glow-green" />
          <div>
            <h1 className="text-lg font-bold text-primary glow-green tracking-wider">
              BALLOON TRACKING SYSTEM
            </h1>
            <p className="text-[10px] text-muted-foreground uppercase tracking-widest">
              PTU Control Interface v1.0
            </p>
          </div>
        </div>
      </div>

      {/* Center: Active Scenario */}
      <ScenarioInfo scenarioId={activeScenario} />

      {/* Right: System Status */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Radio className="w-4 h-4 text-muted-foreground" />
            <StatusIndicator 
              status={systemStatus.connected ? 'online' : 'offline'} 
              label="SYS" 
              size="sm" 
            />
          </div>
          <div className="flex items-center gap-2">
            <Video className="w-4 h-4 text-muted-foreground" />
            <StatusIndicator 
              status={systemStatus.cameraOnline ? 'online' : 'offline'} 
              label="CAM" 
              size="sm" 
            />
          </div>
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-muted-foreground" />
            <StatusIndicator 
              status={systemStatus.ptuOnline ? 'online' : 'offline'} 
              label="PTU" 
              size="sm" 
            />
          </div>
        </div>

        {/* Latency Display */}
        <div className="flex items-center gap-2 px-3 py-1 bg-muted/30 rounded">
          <span className="text-[10px] text-muted-foreground uppercase">Latency</span>
          <span className={cn(
            'font-mono text-sm font-bold',
            systemStatus.latencyMs < 100 ? 'text-tactical-green' : 
            systemStatus.latencyMs < 200 ? 'text-tactical-amber' : 'text-tactical-red'
          )}>
            {systemStatus.latencyMs}ms
          </span>
        </div>

        {/* Time Display */}
        <div className="font-mono text-sm text-tactical-cyan">
          {new Date().toLocaleTimeString('en-US', { hour12: false })}
        </div>
      </div>
    </header>
  );
}
