import { cn } from '@/lib/utils';
import type { LogEntry, LogLevel } from '@/types/tracking';
import { useEffect, useRef } from 'react';

interface LogViewerProps {
  logs: LogEntry[];
  category?: string;
  maxHeight?: string;
  autoScroll?: boolean;
}

const levelColors: Record<LogLevel, string> = {
  info: 'text-tactical-cyan',
  success: 'text-tactical-green glow-green',
  warning: 'text-tactical-amber glow-amber',
  error: 'text-tactical-red glow-red',
};

const levelLabels: Record<LogLevel, string> = {
  info: 'INF',
  success: 'OK ',
  warning: 'WRN',
  error: 'ERR',
};

const categoryColors: Record<string, string> = {
  detection: 'text-blue-400',
  tracking: 'text-green-400',
  ptu: 'text-purple-400',
  kalman: 'text-yellow-400',
  system: 'text-gray-400',
};

export function LogViewer({ logs, category, maxHeight = '400px', autoScroll = true }: LogViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  
  const filteredLogs = category 
    ? logs.filter(log => log.category === category)
    : logs;

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const formatTime = (date: Date) => {
    return date.toISOString().split('T')[1].slice(0, 12);
  };

  return (
    <div 
      ref={containerRef}
      className="font-mono text-xs overflow-y-auto bg-background/50 rounded p-2"
      style={{ maxHeight }}
    >
      {filteredLogs.length === 0 ? (
        <div className="text-muted-foreground text-center py-4">
          No logs available
        </div>
      ) : (
        filteredLogs.map((log) => (
          <div 
            key={log.id} 
            className={cn(
              'flex gap-2 py-0.5 border-b border-border/20 hover:bg-muted/30',
              log.level === 'error' && 'bg-destructive/10'
            )}
          >
            <span className="text-muted-foreground shrink-0">{formatTime(log.timestamp)}</span>
            <span className={cn('shrink-0 font-bold', levelColors[log.level])}>
              [{levelLabels[log.level]}]
            </span>
            <span className={cn('shrink-0 uppercase', categoryColors[log.category] || 'text-gray-400')}>
              [{log.category.slice(0, 4)}]
            </span>
            <span className="text-foreground">{log.message}</span>
          </div>
        ))
      )}
    </div>
  );
}
