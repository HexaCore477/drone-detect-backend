import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import { StatusBadge } from '@/components/tracking/indicators/StatusBadge';
import { Progress } from '@/components/ui/progress';
import { Battery, BatteryCharging } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { BatteryStatus } from '@/types/telemetry';

interface BatteryStatusPanelProps {
  status: BatteryStatus;
}

function formatTime(minutes: number): string {
  if (minutes === 0) return '--:--';
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  return `${hours}h ${mins}m`;
}

export function BatteryStatusPanel({ status }: BatteryStatusPanelProps) {
  const { t } = useTranslation();
  
  const isLow = status.currentPercent < 20;
  const isCritical = status.currentPercent < 10;
  
  return (
    <DataPanel 
      title={t('battery.title', 'Battery')} 
      status={isCritical ? 'error' : isLow ? 'warning' : 'stable'}
    >
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {status.isCharging ? (
              <BatteryCharging className="w-4 h-4 text-[hsl(var(--data-green))]" />
            ) : (
              <Battery className={`w-4 h-4 ${isCritical ? 'text-[hsl(var(--data-red))]' : isLow ? 'text-[hsl(var(--data-amber))]' : 'text-[hsl(var(--data-cyan))]'}`} />
            )}
            <span className={`font-mono text-lg font-bold ${isCritical ? 'text-[hsl(var(--data-red))] glow-red' : isLow ? 'text-[hsl(var(--data-amber))] glow-amber' : 'text-[hsl(var(--data-cyan))]'}`}>
              {status.currentPercent}%
            </span>
          </div>
          {status.isCharging && (
            <StatusBadge label="CHARGING" status="active" />
          )}
        </div>
        <Progress 
          value={status.currentPercent} 
          className="h-2"
        />
        <DataRow 
          label={t('battery.capacity', 'Capacity')} 
          value={status.totalCapacity.toFixed(1)} 
          unit="kWh" 
        />
        {status.isCharging && (
          <DataRow 
            label={t('battery.timeToFull', 'Time to Full')} 
            value={formatTime(status.estimatedChargeTime)} 
          />
        )}
      </div>
    </DataPanel>
  );
}
