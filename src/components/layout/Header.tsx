import { cn } from '@/lib/utils';
import { StatusIndicator } from '@/components/ui/StatusIndicator';
import { ScenarioInfo } from '@/components/tracking/ScenarioSelector';
import { LanguageSwitcher } from '@/components/ui/LanguageSwitcher';
import type { ScenarioId, SystemStatus } from '@/types/tracking';
import { Activity, Radio, Video, Crosshair } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { SkyLANXBranding } from '../tracking/SkyLANXBranding';

interface HeaderProps {
  activeScenario: ScenarioId;
  systemStatus: SystemStatus;
  className?: string;
}

export function Header({ activeScenario, systemStatus, className }: HeaderProps) {
  const { t } = useTranslation();
  
  return (
    <header className={cn(
      'flex items-center justify-between px-4 py-2 bg-card border-b border-border',
      className
    )}>
      {/* Left: System Title */}
      <div className="flex items-center">
          {/* <Crosshair className="w-6 h-6 text-primary glow-green" /> */}
        <SkyLANXBranding /> 
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
              label={t('status.sys')} 
              size="sm" 
            />
          </div>
          <div className="flex items-center gap-2">
            <Video className="w-4 h-4 text-muted-foreground" />
            <StatusIndicator 
              status={systemStatus.cameraOnline ? 'online' : 'offline'} 
              label={t('status.cam')} 
              size="sm" 
            />
          </div>
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-muted-foreground" />
            <StatusIndicator 
              status={systemStatus.ptuOnline ? 'online' : 'offline'} 
              label={t('status.ptu')} 
              size="sm" 
            />
          </div>
        </div>

        {/* Latency Display */}
        <div className="flex items-center gap-2 px-3 py-1 bg-muted/30 rounded">
          <span className="text-[10px] text-muted-foreground uppercase">{t('header.latency')}</span>
          <span className={cn(
            'font-mono text-sm font-bold',
            systemStatus.latencyMs < 100 ? 'text-tactical-green' : 
            systemStatus.latencyMs < 200 ? 'text-tactical-amber' : 'text-tactical-red'
          )}>
            {systemStatus.latencyMs}ms
          </span>
        </div>

        {/* Language Switcher */}
        <LanguageSwitcher />

        {/* Time Display */}
        <div className="font-mono text-sm text-tactical-cyan">
          {new Date().toLocaleTimeString('en-US', { hour12: false })}
        </div>
      </div>
    </header>
  );
}
