import { cn } from '@/lib/utils';
import { ReactNode } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';

interface DataPanelProps {
  title: string;
  children: ReactNode;
  className?: string;
  status?: 'stable' | 'warning' | 'error';
  scrollable?: boolean;
  maxHeight?: string;
}

export function DataPanel({ title, children, className, status, scrollable = false, maxHeight }: DataPanelProps) {
  return (
    <div className={cn('panel overflow-hidden flex flex-col', className)}>
      <div className="panel-header flex items-center justify-between flex-shrink-0">
        <span className="text-primary glow-green">{title}</span>
        {status && (
          <div className={cn('status-dot', {
            'status-stable': status === 'stable',
            'status-warning': status === 'warning',
            'status-error': status === 'error',
          })} />
        )}
      </div>
      {scrollable ? (
        <ScrollArea className="flex-1 min-h-0" style={maxHeight ? { maxHeight } : undefined}>
          <div className="p-3">
            {children}
          </div>
        </ScrollArea>
      ) : (
        <div className="p-3">
          {children}
        </div>
      )}
    </div>
  );
}

interface DataRowProps {
  label: string;
  value: string | number;
  unit?: string;
  highlight?: boolean;
  warning?: boolean;
  error?: boolean;
}

export function DataRow({ label, value, unit, highlight, warning, error }: DataRowProps) {
  return (
    <div className="flex items-center justify-between py-1 border-b border-border/30 last:border-0">
      <span className="data-label">{label}</span>
      <span className={cn('font-mono text-sm tabular-nums', {
        'text-tactical-cyan': !warning && !error,
        'text-tactical-amber glow-amber': warning,
        'text-tactical-red glow-red': error,
        'text-lg font-bold': highlight,
      })}>
        {value}
        {unit && <span className="text-muted-foreground ml-1 text-xs">{unit}</span>}
      </span>
    </div>
  );
}

interface DataGridProps {
  children: ReactNode;
  columns?: 2 | 3 | 4;
  className?: string;
}

export function DataGrid({ children, columns = 2, className }: DataGridProps) {
  return (
    <div className={cn('grid gap-2', {
      'grid-cols-2': columns === 2,
      'grid-cols-3': columns === 3,
      'grid-cols-4': columns === 4,
    }, className)}>
      {children}
    </div>
  );
}

interface DataCellProps {
  label: string;
  value: string | number;
  unit?: string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'success' | 'warning' | 'error';
}

export function DataCell({ label, value, unit, size = 'md', variant = 'default' }: DataCellProps) {
  return (
    <div className="flex flex-col">
      <span className="data-label text-[10px]">{label}</span>
      <span className={cn('font-mono tabular-nums', {
        'text-xs': size === 'sm',
        'text-sm': size === 'md',
        'text-lg font-bold': size === 'lg',
        'text-tactical-cyan': variant === 'default',
        'text-tactical-green glow-green': variant === 'success',
        'text-tactical-amber glow-amber': variant === 'warning',
        'text-tactical-red glow-red': variant === 'error',
      })}>
        {value}{unit && <span className="text-muted-foreground ml-0.5 text-[10px]">{unit}</span>}
      </span>
    </div>
  );
}
