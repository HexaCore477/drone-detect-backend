import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { PTUState } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface PTUDisplayProps {
  state: PTUState;
  className?: string;
}

export function PTUDisplay({ state, className }: PTUDisplayProps) {
  const { t } = useTranslation();
  
  return (
    <DataPanel 
      title={t('ptu.title')} 
      className={className}
      status="stable"
      scrollable
    >
      <div className="space-y-3">
        {/* Azimuth (Pan) Section */}
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">{t('ptu.azimuth')}</div>
          <DataRow 
            label={t('ptu.actual')} 
            value={state.panActual.toFixed(2)} 
            unit="°"
            highlight
          />
        </div>

        {/* Pitch (Tilt) Section */}
        <div>
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">{t('ptu.pitch')}</div>
          <DataRow 
            label={t('ptu.actual')} 
            value={state.tiltActual.toFixed(2)} 
            unit="°"
            highlight
          />
        </div>
      </div>
    </DataPanel>
  );
}
