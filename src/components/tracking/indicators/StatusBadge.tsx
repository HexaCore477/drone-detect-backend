import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  label: string;
  status: 'on' | 'off' | 'active' | 'inactive' | 'warning' | 'error';
  className?: string;
}

export function StatusBadge({ label, status, className }: StatusBadgeProps) {
  const statusStyles = {
    on: 'bg-[hsl(var(--status-stable))] text-primary-foreground',
    active: 'bg-[hsl(var(--status-stable))] text-primary-foreground',
    off: 'bg-muted text-muted-foreground',
    inactive: 'bg-muted text-muted-foreground',
    warning: 'bg-[hsl(var(--status-warning))] text-primary-foreground',
    error: 'bg-[hsl(var(--status-error))] text-primary-foreground animate-pulse',
  };

  return (
    <span className={cn(
      'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider',
      statusStyles[status],
      className
    )}>
      {label}
    </span>
  );
}
