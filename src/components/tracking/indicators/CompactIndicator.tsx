import { cn } from '@/lib/utils';
import { LucideIcon } from 'lucide-react';

interface CompactIndicatorProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  unit?: string;
  variant?: 'default' | 'success' | 'warning' | 'error';
  className?: string;
}

export function CompactIndicator({ 
  icon: Icon, 
  label, 
  value, 
  unit, 
  variant = 'default',
  className 
}: CompactIndicatorProps) {
  return (
    <div className={cn('flex items-center gap-2 px-2 py-1', className)}>
      <Icon className={cn('w-4 h-4 flex-shrink-0', {
        'text-[hsl(var(--data-cyan))]': variant === 'default',
        'text-[hsl(var(--data-green))]': variant === 'success',
        'text-[hsl(var(--data-amber))]': variant === 'warning',
        'text-[hsl(var(--data-red))]': variant === 'error',
      })} />
      <div className="flex flex-col min-w-0">
        <span className="text-[9px] text-muted-foreground uppercase tracking-wide truncate">{label}</span>
        <span className={cn('font-mono text-xs tabular-nums', {
          'text-[hsl(var(--data-cyan))]': variant === 'default',
          'text-[hsl(var(--data-green))]': variant === 'success',
          'text-[hsl(var(--data-amber))]': variant === 'warning',
          'text-[hsl(var(--data-red))]': variant === 'error',
        })}>
          {value}{unit && <span className="text-muted-foreground ml-0.5">{unit}</span>}
        </span>
      </div>
    </div>
  );
}
