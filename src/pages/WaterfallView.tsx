import { DataPanel } from '@/components/ui/DataPanel';
import { LogViewer } from '@/components/tracking/LogViewer';
import type { LogEntry, PTUState, KalmanState } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface WaterfallViewProps {
  logs: LogEntry[];
  ptuState: PTUState;
  kalmanState: KalmanState;
}

export function WaterfallView({ logs, ptuState, kalmanState }: WaterfallViewProps) {
  const { t } = useTranslation();
  
  return (
    <div className="h-full grid grid-cols-3 gap-4 p-4">
      {/* Column A: Detection & Tracking Logs */}
      <div className="flex flex-col gap-4">
        <DataPanel title={t('waterfall.detectionEvents')} status="stable" className="flex-1">
          <LogViewer 
            logs={logs} 
            category="detection" 
            maxHeight="calc(50vh - 100px)"
          />
        </DataPanel>
        <DataPanel title={t('waterfall.trackingStatus')} status="stable" className="flex-1">
          <LogViewer 
            logs={logs} 
            category="tracking" 
            maxHeight="calc(50vh - 100px)"
          />
        </DataPanel>
      </div>

      {/* Column B: Kalman / Prediction / Latency */}
      <div className="flex flex-col gap-4">
        <DataPanel title={t('waterfall.kalmanFilterLog')} status="stable" className="flex-1">
          <LogViewer 
            logs={logs} 
            category="kalman" 
            maxHeight="calc(33vh - 80px)"
          />
        </DataPanel>
        <DataPanel title={t('waterfall.predictionState')} status="stable" className="flex-1">
          <div className="font-mono text-xs space-y-2">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-[10px] text-muted-foreground">{t('kalman.filterMode')}</div>
                <div className={kalmanState.predicting ? 'text-tactical-amber' : 'text-tactical-green'}>
                  {kalmanState.predicting ? t('kalman.predicting') : t('kalman.updating')}
                </div>
              </div>
              <div>
                <div className="text-[10px] text-muted-foreground">{t('kalman.gating')}</div>
                <div className={kalmanState.gatingActive ? 'text-tactical-amber' : 'text-tactical-cyan'}>
                  {kalmanState.gatingActive ? t('kalman.rejecting') : t('kalman.passing')}
                </div>
              </div>
            </div>
            <div className="border-t border-border/50 pt-2">
              <div className="text-[10px] text-muted-foreground mb-1">{t('kalman.stateCovariance')}</div>
              <div className="grid grid-cols-4 gap-1 text-[10px]">
                {[0.12, 0.01, 0.02, 0.00].map((v, i) => (
                  <div key={i} className="bg-muted/30 p-1 text-center text-tactical-cyan">
                    {v.toFixed(2)}
                  </div>
                ))}
                {[0.01, 0.15, 0.00, 0.03].map((v, i) => (
                  <div key={i} className="bg-muted/30 p-1 text-center text-tactical-cyan">
                    {v.toFixed(2)}
                  </div>
                ))}
                {[0.02, 0.00, 0.08, 0.01].map((v, i) => (
                  <div key={i} className="bg-muted/30 p-1 text-center text-tactical-cyan">
                    {v.toFixed(2)}
                  </div>
                ))}
                {[0.00, 0.03, 0.01, 0.10].map((v, i) => (
                  <div key={i} className="bg-muted/30 p-1 text-center text-tactical-cyan">
                    {v.toFixed(2)}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </DataPanel>
        <DataPanel title={t('waterfall.latencyCompensation')} status="stable" className="flex-1">
          <div className="font-mono text-xs space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">{t('kalman.leadTime')}</span>
              <span className="text-tactical-cyan">200 ms</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">u_lead</span>
              <span className="text-tactical-cyan">642.50</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-muted-foreground">v_lead</span>
              <span className="text-tactical-cyan">358.30</span>
            </div>
            <div className="border-t border-border/50 pt-2 mt-2">
              <div className="text-[10px] text-muted-foreground mb-1">{t('kalman.leadVector')}</div>
              <div className="flex items-center gap-4">
                <div className="flex-1 h-1 bg-muted rounded">
                  <div className="h-full bg-primary w-1/4 rounded" />
                </div>
                <span className="text-tactical-cyan">Δu: 2.50</span>
              </div>
              <div className="flex items-center gap-4 mt-1">
                <div className="flex-1 h-1 bg-muted rounded">
                  <div className="h-full bg-primary w-1/6 rounded" />
                </div>
                <span className="text-tactical-cyan">Δv: -1.70</span>
              </div>
            </div>
          </div>
        </DataPanel>
      </div>

      {/* Column C: PTU / Emitter / Alignment */}
      <div className="flex flex-col gap-4">
        <DataPanel title={t('waterfall.ptuCommands')} status="stable" className="flex-1">
          <LogViewer 
            logs={logs} 
            category="ptu" 
            maxHeight="calc(33vh - 80px)"
          />
        </DataPanel>
        <DataPanel title={t('waterfall.ptuState')} status="stable" className="flex-1">
          <div className="font-mono text-xs space-y-3">
            <div>
              <div className="text-[10px] text-muted-foreground mb-1">{t('waterfall.panAxis')}</div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <div className="text-[9px] text-muted-foreground">{t('ptu.target')}</div>
                  <div className="text-tactical-cyan">{ptuState.panTarget.toFixed(2)}°</div>
                </div>
                <div>
                  <div className="text-[9px] text-muted-foreground">{t('ptu.actual').toUpperCase()}</div>
                  <div className="text-tactical-green">{ptuState.panActual.toFixed(2)}°</div>
                </div>
                <div>
                  <div className="text-[9px] text-muted-foreground">{t('ptu.error')}</div>
                  <div className="text-tactical-amber">
                    {(ptuState.panTarget - ptuState.panActual).toFixed(2)}°
                  </div>
                </div>
              </div>
            </div>
            <div>
              <div className="text-[10px] text-muted-foreground mb-1">{t('waterfall.tiltAxis')}</div>
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <div className="text-[9px] text-muted-foreground">{t('ptu.target')}</div>
                  <div className="text-tactical-cyan">{ptuState.tiltTarget.toFixed(2)}°</div>
                </div>
                <div>
                  <div className="text-[9px] text-muted-foreground">{t('ptu.actual').toUpperCase()}</div>
                  <div className="text-tactical-green">{ptuState.tiltActual.toFixed(2)}°</div>
                </div>
                <div>
                  <div className="text-[9px] text-muted-foreground">{t('ptu.error')}</div>
                  <div className="text-tactical-amber">
                    {(ptuState.tiltTarget - ptuState.tiltActual).toFixed(2)}°
                  </div>
                </div>
              </div>
            </div>
          </div>
        </DataPanel>
        <DataPanel title={t('waterfall.systemLog')} status="stable" className="flex-1">
          <LogViewer 
            logs={logs} 
            category="system" 
            maxHeight="calc(33vh - 80px)"
          />
        </DataPanel>
      </div>
    </div>
  );
}
