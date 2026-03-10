import { useEffect, useRef, useState } from 'react';
import { DataPanel } from '@/components/ui/DataPanel';
import { LogViewer } from '@/components/tracking/LogViewer';
import type { LogEntry, DetectedBalloon } from '@/types/tracking';
import type { KalmanFilterData } from '@/hooks/useBalloonTracking';
import { useTranslation } from 'react-i18next';

const MAX_TRACKING_ENTRIES = 100;

interface TrackingStatusLogProps {
  logs: LogEntry[];
  balloons?: DetectedBalloon[];
  balloonTimestamp?: number | null;
  kalmanData?: KalmanFilterData | null;
}

function trackingToLogEntries(
  balloons: DetectedBalloon[],
  balloonTimestamp: number,
  kalmanData: KalmanFilterData | null
): LogEntry[] {
  const ts = new Date(balloonTimestamp);
  const entries: LogEntry[] = [];
  const targetCount = balloons.filter((b) => b.isTarget).length;
  const totalCount = balloons.length;

  if (totalCount > 0) {
    entries.push({
      id: `trk-status-${balloonTimestamp}`,
      timestamp: ts,
      level: 'success',
      category: 'tracking',
      message: `Tracking active: ${totalCount} detected, ${targetCount} target(s)`,
    });
  } else {
    entries.push({
      id: `trk-status-${balloonTimestamp}`,
      timestamp: ts,
      level: 'info',
      category: 'tracking',
      message: 'Tracking idle: no targets',
    });
  }

  if (kalmanData) {
    entries.push({
      id: `trk-kalman-${balloonTimestamp}`,
      timestamp: ts,
      level: 'info',
      category: 'tracking',
      message: `Kalman track ${kalmanData.trackId}: pred=(${kalmanData.predX.toFixed(0)}, ${kalmanData.predY.toFixed(0)}) meas=(${kalmanData.measurementX.toFixed(0)}, ${kalmanData.measurementY.toFixed(0)})`,
    });
  }

  return entries;
}

export function TrackingStatusLog({
  logs,
  balloons = [],
  balloonTimestamp = null,
  kalmanData = null,
}: TrackingStatusLogProps) {
  const { t } = useTranslation();
  const [trackingEntries, setTrackingEntries] = useState<LogEntry[]>([]);
  const prevTimestampRef = useRef<number | null>(null);

  useEffect(() => {
    if (balloonTimestamp == null) return;
    if (prevTimestampRef.current === balloonTimestamp) return;
    prevTimestampRef.current = balloonTimestamp;

    const newEntries = trackingToLogEntries(balloons, balloonTimestamp, kalmanData);
    setTrackingEntries((prev) => {
      const merged = [...prev, ...newEntries];
      return merged.slice(-MAX_TRACKING_ENTRIES);
    });
  }, [balloons, balloonTimestamp, kalmanData]);

  const allLogs = [
    ...logs.filter((l) => l.category === 'tracking'),
    ...trackingEntries,
  ].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

  const status = balloons.length > 0 ? 'stable' : undefined;

  return (
    <DataPanel title={t('waterfall.trackingStatus')} status={status} className="flex-1">
      <LogViewer logs={allLogs} category="tracking" />
    </DataPanel>
  );
}

