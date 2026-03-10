import { useEffect, useRef, useState } from 'react';
import { DataPanel } from '@/components/ui/DataPanel';
import { LogViewer } from '@/components/tracking/LogViewer';
import type { LogEntry, DetectedBalloon } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

const MAX_DETECTION_ENTRIES = 100;

interface DetectionEventsLogProps {
  logs: LogEntry[];
  balloons?: DetectedBalloon[];
  balloonTimestamp?: number | null;
}

function balloonToLogEntries(
  balloons: DetectedBalloon[],
  timestamp: number
): LogEntry[] {
  const ts = new Date(timestamp);
  return balloons.map((b) => {
    const conf = (b.confidence ?? 0) * 100;
    const msg = b.isTarget
      ? `Balloon ${b.id} (${b.color}) at (${b.centerX.toFixed(0)}, ${b.centerY.toFixed(0)}) conf=${conf.toFixed(0)}% [TARGET]`
      : `Balloon ${b.id} (${b.color}) at (${b.centerX.toFixed(0)}, ${b.centerY.toFixed(0)}) conf=${conf.toFixed(0)}%`;
    return {
      id: `det-${timestamp}-${b.id}`,
      timestamp: ts,
      level: 'info' as const,
      category: 'detection' as const,
      message: msg,
    };
  });
}

export function DetectionEventsLog({ logs, balloons = [], balloonTimestamp = null }: DetectionEventsLogProps) {
  const { t } = useTranslation();
  const [detectionEntries, setDetectionEntries] = useState<LogEntry[]>([]);
  const prevTimestampRef = useRef<number | null>(null);

  useEffect(() => {
    if (balloons.length === 0 || balloonTimestamp == null) return;
    if (prevTimestampRef.current === balloonTimestamp) return;
    prevTimestampRef.current = balloonTimestamp;

    const newEntries = balloonToLogEntries(balloons, balloonTimestamp);
    setDetectionEntries((prev) => {
      const merged = [...prev, ...newEntries];
      return merged.slice(-MAX_DETECTION_ENTRIES);
    });
  }, [balloons, balloonTimestamp]);

  const allLogs = [
    ...logs.filter((l) => l.category === 'detection'),
    ...detectionEntries,
  ].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

  return (
    <DataPanel title={t('waterfall.detectionEvents')} status="stable" className="flex-1">
      <LogViewer logs={allLogs} category="detection" />
    </DataPanel>
  );
}

