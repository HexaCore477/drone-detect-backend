import { DataPanel, DataRow, DataGrid, DataCell } from '@/components/ui/DataPanel';
import { MapPin, Navigation } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { PlatformStatus } from '@/types/telemetry';

interface PlatformStatusPanelProps {
  status: PlatformStatus;
}

function formatCoordinate(value: number, isLatitude: boolean): string {
  const absolute = Math.abs(value);
  const degrees = Math.floor(absolute);
  const minutes = (absolute - degrees) * 60;
  const direction = isLatitude 
    ? (value >= 0 ? 'N' : 'S')
    : (value >= 0 ? 'E' : 'W');
  return `${degrees}°${minutes.toFixed(3)}'${direction}`;
}

export function PlatformStatusPanel({ status }: PlatformStatusPanelProps) {
  const { t } = useTranslation();
  
  return (
    <DataPanel title={t('platform.title', 'Platform Status')} status="stable">
      <div className="space-y-2">
        {/* Attitude */}
        <div className="border-b border-border/30 pb-2">
          <span className="data-label block mb-1">{t('platform.attitude', 'Attitude')}</span>
          <DataGrid columns={3}>
            <DataCell 
              label="Roll" 
              value={status.attitude.roll.toFixed(1)} 
              unit="°" 
              size="sm"
            />
            <DataCell 
              label="Pitch" 
              value={status.attitude.pitch.toFixed(1)} 
              unit="°" 
              size="sm"
            />
            <DataCell 
              label="Yaw" 
              value={status.attitude.yaw.toFixed(1)} 
              unit="°" 
              size="sm"
            />
          </DataGrid>
        </div>
        
        {/* GPS Coordinates */}
        <div className="space-y-1">
          <div className="flex items-center gap-1 mb-1">
            <MapPin className="w-3 h-3 text-[hsl(var(--data-cyan))]" />
            <span className="data-label">{t('platform.gps', 'GPS')}</span>
          </div>
          <div className="font-mono text-xs text-[hsl(var(--data-cyan))] space-y-0.5">
            <div>{formatCoordinate(status.geoPosition.latitude, true)}</div>
            <div>{formatCoordinate(status.geoPosition.longitude, false)}</div>
          </div>
        </div>
        
        {/* Altitude */}
        <DataRow 
          label={t('platform.altitude', 'Altitude')} 
          value={status.geoPosition.altitude.toFixed(0)} 
          unit="m" 
        />
      </div>
    </DataPanel>
  );
}
