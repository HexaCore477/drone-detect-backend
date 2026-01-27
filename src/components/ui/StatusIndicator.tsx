import { cn } from '@/lib/utils';

interface StatusIndicatorProps {
  status: 'online' | 'offline' | 'warning' | 'active' | 'idle';
  label: string;
  size?: 'sm' | 'md' | 'lg';
}

export function StatusIndicator({ status, label, size = 'md' }: StatusIndicatorProps) {
  return (
    <div className="flex items-center gap-2">
      <div className={cn('rounded-full', {
        'w-2 h-2': size === 'sm',
        'w-3 h-3': size === 'md',
        'w-4 h-4': size === 'lg',
        'bg-tactical-green shadow-[0_0_8px_hsl(var(--status-stable))] animate-pulse': status === 'online' || status === 'active',
        'bg-tactical-red shadow-[0_0_8px_hsl(var(--status-error))]': status === 'offline',
        'bg-tactical-amber shadow-[0_0_8px_hsl(var(--status-warning))] animate-pulse': status === 'warning',
        'bg-muted-foreground': status === 'idle',
      })} />
      <span className={cn('uppercase tracking-wider', {
        'text-[10px]': size === 'sm',
        'text-xs': size === 'md',
        'text-sm': size === 'lg',
        'text-tactical-green': status === 'online' || status === 'active',
        'text-tactical-red': status === 'offline',
        'text-tactical-amber': status === 'warning',
        'text-muted-foreground': status === 'idle',
      })}>
        {label}
      </span>
    </div>
  );
}

interface StatusBarProps {
  items: Array<{ status: 'online' | 'offline' | 'warning'; label: string }>;
}

export function StatusBar({ items }: StatusBarProps) {
  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-card border-b border-border">
      {items.map((item, index) => (
        <StatusIndicator key={index} status={item.status} label={item.label} size="sm" />
      ))}
    </div>
  );
}
