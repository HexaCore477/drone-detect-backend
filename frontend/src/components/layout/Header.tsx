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
      {/* <ScenarioInfo scenarioId={activeScenario} /> */}

      {/* Right: System Status */}
      <div className="flex items-center gap-6">
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
