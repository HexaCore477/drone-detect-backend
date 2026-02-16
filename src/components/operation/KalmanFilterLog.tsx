import { useEffect, useRef, useState } from 'react';
import { DataPanel } from '@/components/ui/DataPanel';
import { LogViewer } from '@/components/tracking/LogViewer';
import type { LogEntry } from '@/types/tracking';
import type { KalmanFilterData } from '@/hooks/useBalloonTracking';
import { useTranslation } from 'react-i18next';

const MAX_KALMAN_ENTRIES = 100;

interface KalmanFilterLogProps {
  logs: LogEntry[];
  kalmanData?: KalmanFilterData | null;
  kalmanTimestamp?: number | null;
}

function kalmanToLogEntries(k: KalmanFilterData, timestamp: number): LogEntry[] {
  const ts = new Date(timestamp);
  return [
    {
      id: `kalman-${timestamp}-state`,
      timestamp: ts,
      level: 'info' as const,
      category: 'kalman' as const,
      message: `Kalman state [${k.trackId}] x=${k.x.toFixed(1)} y=${k.y.toFixed(1)} vx=${k.vx.toFixed(2)} vy=${k.vy.toFixed(2)}`,
    },
    {
      id: `kalman-${timestamp}-pred`,
      timestamp: ts,
      level: 'info' as const,
      category: 'kalman' as const,
      message: `Prediction (500ms) predX=${k.predX.toFixed(1)} predY=${k.predY.toFixed(1)}`,
    },
    {
      id: `kalman-${timestamp}-meas`,
      timestamp: ts,
      level: 'info' as const,
      category: 'kalman' as const,
      message: `Measurement measX=${k.measurementX.toFixed(1)} measY=${k.measurementY.toFixed(1)}`,
    },
  ];
}

export function KalmanFilterLog({ logs, kalmanData = null, kalmanTimestamp = null }: KalmanFilterLogProps) {
  const { t } = useTranslation();
  const [kalmanEntries, setKalmanEntries] = useState<LogEntry[]>([]);
  const prevTimestampRef = useRef<number | null>(null);

  useEffect(() => {
    if (!kalmanData || kalmanTimestamp == null) return;
    if (prevTimestampRef.current === kalmanTimestamp) return;
    prevTimestampRef.current = kalmanTimestamp;

    const newEntries = kalmanToLogEntries(kalmanData, kalmanTimestamp);
    setKalmanEntries((prev) => {
      const merged = [...prev, ...newEntries];
      return merged.slice(-MAX_KALMAN_ENTRIES);
    });
  }, [kalmanData, kalmanTimestamp]);

  const allLogs = [
    ...logs.filter((l) => l.category === 'kalman'),
    ...kalmanEntries,
  ].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

  return (
    <DataPanel title={t('waterfall.kalmanFilterLog')} status="stable" className="flex-1">
      <LogViewer logs={allLogs} category="kalman" />
    </DataPanel>
  );
}

