import { DataPanel, DataRow, DataGrid, DataCell } from '@/components/ui/DataPanel';
import type { KalmanState } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface KalmanDisplayProps {
  state: KalmanState;
  className?: string;
}

export function KalmanDisplay({ state, className }: KalmanDisplayProps) {
  const { t } = useTranslation();
  const timeSinceUpdate = Date.now() - state.lastUpdate;
  const isStale = timeSinceUpdate > 500;
  
  return (
    <DataPanel 
      title={t('kalman.title')} 
      className={className}
      status={!state.enabled ? 'warning' : isStale ? 'error' : 'stable'}
      scrollable
    >
      <div className="space-y-3">
        <DataGrid columns={2}>
          <DataCell 
            label={t('kalman.status')} 
            value={state.enabled ? t('kalman.enabled') : t('kalman.disabled')} 
            variant={state.enabled ? 'success' : 'warning'}
            size="sm"
          />
          <DataCell 
            label={t('kalman.mode')} 
            value={state.predicting ? t('kalman.predict') : t('kalman.update')} 
            variant={state.predicting ? 'warning' : 'default'}
            size="sm"
          />
        </DataGrid>

        <DataRow 
          label={t('kalman.gating')} 
          value={state.gatingActive ? t('kalman.active') : t('kalman.inactive')}
          warning={state.gatingActive}
        />
        
        <DataRow 
          label={t('kalman.lastUpdate')} 
          value={timeSinceUpdate} 
          unit="ms"
          warning={timeSinceUpdate > 200}
          error={isStale}
        />

        {/* State Vector Visualization */}
        <div className="pt-2 border-t border-border/50">
          <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">{t('kalman.stateVector')}</div>
          <div className="grid grid-cols-2 gap-2 font-mono text-xs">
            <div className="bg-muted/30 p-2 rounded">
              <div className="text-[10px] text-muted-foreground">u</div>
              <div className="text-tactical-cyan">640.00</div>
            </div>
            <div className="bg-muted/30 p-2 rounded">
              <div className="text-[10px] text-muted-foreground">v</div>
              <div className="text-tactical-cyan">360.00</div>
            </div>
            <div className="bg-muted/30 p-2 rounded">
              <div className="text-[10px] text-muted-foreground">u̇</div>
              <div className="text-tactical-cyan">0.00</div>
            </div>
            <div className="bg-muted/30 p-2 rounded">
              <div className="text-[10px] text-muted-foreground">v̇</div>
              <div className="text-tactical-cyan">0.00</div>
            </div>
          </div>
        </div>
      </div>
    </DataPanel>
  );
}
