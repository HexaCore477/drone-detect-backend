import { DataPanel, DataRow, DataGrid, DataCell } from '@/components/ui/DataPanel';
import { 
  Thermometer, 
  Wind, 
  Droplets, 
  Gauge,
  Cloud,
  CloudRain,
  CloudSnow,
  CloudFog,
  Sun
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { EnvironmentStatus } from '@/types/telemetry';

interface EnvironmentPanelProps {
  status: EnvironmentStatus;
}

const weatherIcons: Record<EnvironmentStatus['weatherCondition'], React.ElementType> = {
  clear: Sun,
  fog: CloudFog,
  rain: CloudRain,
  snow: CloudSnow,
  overcast: Cloud,
};

const weatherLabels: Record<EnvironmentStatus['weatherCondition'], string> = {
  clear: 'Clear',
  fog: 'Fog',
  rain: 'Rain',
  snow: 'Snow',
  overcast: 'Overcast',
};

function getWindDirection(degrees: number): string {
  const directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  const index = Math.round(degrees / 45) % 8;
  return directions[index];
}

export function EnvironmentPanel({ status }: EnvironmentPanelProps) {
  const { t } = useTranslation();
  const WeatherIcon = weatherIcons[status.weatherCondition];
  
  return (
    <DataPanel title={t('environment.title', 'Environment')} status="stable">
      <div className="space-y-2">
        {/* Weather Condition */}
        <div className="flex items-center justify-between py-1 border-b border-border/30">
          <span className="data-label">{t('environment.weather', 'Weather')}</span>
          <div className="flex items-center gap-2">
            <WeatherIcon className="w-4 h-4 text-[hsl(var(--data-cyan))]" />
            <span className="font-mono text-sm text-[hsl(var(--data-cyan))]">
              {weatherLabels[status.weatherCondition]}
            </span>
          </div>
        </div>
        
        <DataGrid columns={2}>
          <DataCell 
            label={t('environment.temp', 'Temp')} 
            value={status.temperature.toFixed(1)} 
            unit="°C" 
            size="sm"
          />
          <DataCell 
            label={t('environment.humidity', 'Humidity')} 
            value={status.humidity} 
            unit="%" 
            size="sm"
          />
          <DataCell 
            label={t('environment.pressure', 'Pressure')} 
            value={status.airPressure.toFixed(0)} 
            unit="hPa" 
            size="sm"
          />
          <DataCell 
            label={t('environment.windSpeed', 'Wind')} 
            value={status.windSpeed.toFixed(1)} 
            unit="m/s" 
            size="sm"
          />
        </DataGrid>
        
        <div className="flex items-center justify-between pt-1 border-t border-border/30">
          <span className="data-label">{t('environment.windDir', 'Wind Dir')}</span>
          <span className="font-mono text-sm text-[hsl(var(--data-cyan))]">
            {status.windDirection}° ({getWindDirection(status.windDirection)})
          </span>
        </div>
      </div>
    </DataPanel>
  );
}
