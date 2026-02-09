import { useCallback, useEffect, useState } from 'react';
import { getPtuPorts, getPtuConnectStatus, ptuDirection, ptuConnect, ptuDisconnect, getAutoTracking, setAutoTracking } from '@/api';
import { DataPanel } from '@/components/ui/DataPanel';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { useToast } from '@/hooks/use-toast';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { 
  ChevronLeft, 
  ChevronRight, 
  ChevronUp, 
  ChevronDown, 
  Pause,
  Plug,
  PlugZap,
  RefreshCw,
  Settings,
  ArrowUpLeft,
  ArrowUpRight,
  ArrowDownLeft,
  ArrowDownRight
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { PTUState } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface PTUControlProps {
  ptuState?: PTUState;
  className?: string;
}

const baudRates = ['9600', '19200', '38400', '57600', '115200'];

export function PTUControl({ ptuState, className }: PTUControlProps) {
  const { t } = useTranslation();
  const { toast } = useToast();
  const [serialPorts, setSerialPorts] = useState<string[]>([]);
  const [serialPort, setSerialPort] = useState<string>('');
  const [baudRate, setBaudRate] = useState<string>('9600');
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isAutoTracking, setIsAutoTracking] = useState<boolean>(false);
  const [portsLoading, setPortsLoading] = useState<boolean>(false);

  // On initial mount / page refresh, query backend connection status and auto-tracking config
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [status, config] = await Promise.all([
          getPtuConnectStatus(),
          getAutoTracking(),
        ]);
        if (!cancelled) {
          setIsConnected(status.connected);
          setIsAutoTracking(config.is_auto_tracking);
        }
      } catch (err) {
        console.warn('Failed to fetch initial state:', err);
        if (!cancelled) {
          setIsConnected(false);
          setIsAutoTracking(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const fetchPorts = useCallback(async () => {
    setPortsLoading(true);
    try {
      const ports = await getPtuPorts();
      setSerialPorts(ports);
      setSerialPort((prev) => (ports.length > 0 && !prev ? ports[0] : prev));
    } catch (err) {
      console.warn('Failed to fetch serial ports:', err);
      setSerialPorts([]);
      toast({
        variant: 'destructive',
        title: t('ptu.error.fetchPorts'),
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setPortsLoading(false);
    }
  }, [t, toast]);

  useEffect(() => {
    fetchPorts();
  }, [fetchPorts]);

  const handleConnect = async () => {
    if (isConnected) {
      try {
        await ptuDisconnect();
        setIsConnected(false);
        toast({
          variant: 'default',
          title: t('ptu.success.disconnected'),
          description: t('ptu.success.disconnectedDesc'),
        });
      } catch (err) {
        console.error('PTU disconnect failed:', err);
        toast({
          variant: 'destructive',
          title: t('ptu.error.disconnect'),
          description: err instanceof Error ? err.message : String(err),
        });
      }
    } else {
      if (!serialPort || serialPort === '_empty') {
        toast({
          variant: 'destructive',
          title: t('ptu.error.noPort'),
          description: t('ptu.error.noPortDesc'),
        });
        return;
      }
      try {
        await ptuConnect({ port: serialPort, baud: parseInt(baudRate, 10) });
        setIsConnected(true);
        toast({
          variant: 'default',
          title: t('ptu.success.connected'),
          description: `${t('ptu.success.connectedDesc')} ${serialPort} @ ${baudRate} baud`,
        });
      } catch (err) {
        console.error('PTU connect failed:', err);
        toast({
          variant: 'destructive',
          title: t('ptu.error.connect'),
          description: err instanceof Error ? err.message : String(err),
        });
      }
    }
  };

  const handleControl = async (direction: 'left' | 'right' | 'up' | 'down' | 'pause' | 'left-up' | 'left-down' | 'right-up' | 'right-down') => {
    if (!isConnected) {
      toast({
        variant: 'destructive',
        title: t('ptu.error.notConnected'),
        description: t('ptu.error.notConnectedDesc'),
      });
      return;
    }
    try {
      await ptuDirection(direction);
    } catch (err) {
      console.error('PTU direction failed:', err);
      toast({
        variant: 'destructive',
        title: t('ptu.error.direction'),
        description: err instanceof Error ? err.message : String(err),
      });
    }
  };

  return (
    <DataPanel 
      title={t('ptu.control')} 
      className={className}
      status={isConnected ? 'stable' : 'warning'}
      scrollable
    >
      <div className="space-y-4">
        {/* Serial Port Connection Section */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-border/50">
            <Settings className="w-4 h-4 text-primary" />
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
              {t('ptu.serialConnection')}
            </div>
          </div>

          {/* Serial Port Name and Baud Rate - One Line */}
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label className="text-[10px] text-muted-foreground uppercase tracking-wider">
                  {t('ptu.serialPort')}
                </Label>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={fetchPorts}
                  disabled={portsLoading || isConnected}
                  title={t('ptu.refreshPorts')}
                >
                  <RefreshCw className={cn('h-3.5 w-3.5', portsLoading && 'animate-spin')} />
                </Button>
              </div>
              <Select
                value={serialPorts.length === 0 ? '_empty' : serialPort || serialPorts[0]}
                onValueChange={(v) => v !== '_empty' && setSerialPort(v)}
                disabled={isConnected || portsLoading}
              >
                <SelectTrigger className="h-8 text-xs font-mono">
                  <SelectValue placeholder={portsLoading ? t('ptu.loadingPorts') : t('ptu.selectPort')} />
                </SelectTrigger>
                <SelectContent>
                  {serialPorts.length === 0 && !portsLoading ? (
                    <SelectItem value="_empty" className="font-mono text-muted-foreground" disabled>
                      {t('ptu.noPorts')}
                    </SelectItem>
                  ) : (
                    serialPorts.map((port) => (
                      <SelectItem key={port} value={port} className="font-mono">
                        {port}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-[10px] text-muted-foreground uppercase tracking-wider">
                {t('ptu.baudRate')}
              </Label>
              <Select value={baudRate} onValueChange={setBaudRate} disabled={isConnected}>
                <SelectTrigger className="h-8 text-xs font-mono">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {baudRates.map((rate) => (
                    <SelectItem key={rate} value={rate} className="font-mono">
                      {rate}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Connect Button */}
          <Button
            onClick={handleConnect}
            variant={isConnected ? 'destructive' : 'default'}
            className={cn(
              'w-full h-9 font-mono text-xs',
              isConnected && 'bg-destructive/20 border border-destructive/50 text-destructive hover:bg-destructive/30'
            )}
          >
            {isConnected ? (
              <>
                <PlugZap className="w-4 h-4" />
                {t('ptu.disconnect')}
              </>
            ) : (
              <>
                <Plug className="w-4 h-4" />
                {t('ptu.connect')}
              </>
            )}
          </Button>

          {/* Connection Status */}
          <div className="flex items-center justify-between px-2 py-1.5 bg-muted/20 rounded border border-border/50">
            <span className="text-[10px] text-muted-foreground uppercase">{t('kalman.status')}:</span>
            <div className="flex items-center gap-2">
              <div className={cn(
                'w-2 h-2 rounded-full',
                isConnected ? 'bg-tactical-green shadow-[0_0_8px_hsl(var(--status-stable))]' : 'bg-tactical-amber'
              )} />
              <span className={cn(
                'text-xs font-mono',
                isConnected ? 'text-tactical-green' : 'text-tactical-amber'
              )}>
                {isConnected ? t('status.connected') : t('status.disconnected')}
              </span>
            </div>
          </div>
        </div>

        {/* Control Section */}
        <div className="space-y-3 pt-2 border-t border-border/50">
          <div className="flex items-center gap-2 pb-2">
            <Settings className="w-4 h-4 text-primary" />
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
              {t('ptu.controlSection')}
            </div>
          </div>

          {/* Auto/Manual Tracking Checkbox */}
          <div className="flex items-center space-x-2 p-2 bg-muted/20 rounded border border-border/50">
            <Checkbox
              id="auto-tracking"
              checked={isAutoTracking}
              onCheckedChange={async (checked) => {
                const newValue = checked === true;
                setIsAutoTracking(newValue);
                try {
                  await setAutoTracking(newValue);
                } catch (err) {
                  console.error('Failed to save auto-tracking config:', err);
                  toast({
                    variant: 'destructive',
                    title: t('ptu.error.direction'),
                    description: err instanceof Error ? err.message : 'Failed to save config',
                  });
                  // Revert on error
                  setIsAutoTracking(!newValue);
                }
              }}
              disabled={!isConnected}
              className="border-primary data-[state=checked]:bg-primary"
            />
            <Label
              htmlFor="auto-tracking"
              className="text-xs font-mono cursor-pointer flex-1"
            >
              {t('ptu.autoTracking')}
            </Label>
            <span className={cn(
              'text-[10px] font-mono px-2 py-0.5 rounded',
              isAutoTracking 
                ? 'bg-tactical-green/20 text-tactical-green border border-tactical-green/50' 
                : 'bg-tactical-amber/20 text-tactical-amber border border-tactical-amber/50'
            )}>
              {isAutoTracking ? t('camera.auto') : t('camera.manual')}
            </span>
          </div>

          {/* Control Buttons */}
          <div className="space-y-2">
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
              {t('ptu.manualControl')} {!isAutoTracking && t('ptu.active')}
            </div>
            
            {/* Top Row: Left-Up, Up, Right-Up */}
            <div className="flex items-center justify-center gap-2">
              <Button
                onClick={() => handleControl('left-up')}
                disabled={!isConnected || isAutoTracking}
                variant="outline"
                size="icon"
                className={cn(
                  'h-9 w-9 border-primary/50',
                  !isConnected || isAutoTracking ? 'opacity-50' : 'hover:bg-primary/20 hover:border-primary'
                )}
              >
                <ArrowUpLeft className="w-4 h-4" />
              </Button>
              
              <Button
                onClick={() => handleControl('up')}
                disabled={!isConnected || isAutoTracking}
                variant="outline"
                size="icon"
                className={cn(
                  'h-10 w-10 border-primary/50',
                  !isConnected || isAutoTracking ? 'opacity-50' : 'hover:bg-primary/20 hover:border-primary'
                )}
              >
                <ChevronUp className="w-5 h-5" />
              </Button>
              
              <Button
                onClick={() => handleControl('right-up')}
                disabled={!isConnected || isAutoTracking}
                variant="outline"
                size="icon"
                className={cn(
                  'h-9 w-9 border-primary/50',
                  !isConnected || isAutoTracking ? 'opacity-50' : 'hover:bg-primary/20 hover:border-primary'
                )}
              >
                <ArrowUpRight className="w-4 h-4" />
              </Button>
            </div>

            {/* Middle Row: Left, Pause, Right */}
            <div className="flex items-center justify-center gap-2">
              <Button
                onClick={() => handleControl('left')}
                disabled={!isConnected || isAutoTracking}
                variant="outline"
                size="icon"
                className={cn(
                  'h-10 w-10 border-primary/50',
                  !isConnected || isAutoTracking ? 'opacity-50' : 'hover:bg-primary/20 hover:border-primary'
                )}
              >
                <ChevronLeft className="w-5 h-5" />
              </Button>

              <Button
                onClick={() => handleControl('pause')}
                disabled={!isConnected}
                variant="outline"
                size="icon"
                className={cn(
                  'h-10 w-10 border-tactical-amber/50',
                  !isConnected ? 'opacity-50' : 'hover:bg-tactical-amber/20 hover:border-tactical-amber'
                )}
              >
                <Pause className="w-4 h-4" />
              </Button>

              <Button
                onClick={() => handleControl('right')}
                disabled={!isConnected || isAutoTracking}
                variant="outline"
                size="icon"
                className={cn(
                  'h-10 w-10 border-primary/50',
                  !isConnected || isAutoTracking ? 'opacity-50' : 'hover:bg-primary/20 hover:border-primary'
                )}
              >
                <ChevronRight className="w-5 h-5" />
              </Button>
            </div>

            {/* Bottom Row: Left-Down, Down, Right-Down */}
            <div className="flex items-center justify-center gap-2">
              <Button
                onClick={() => handleControl('left-down')}
                disabled={!isConnected || isAutoTracking}
                variant="outline"
                size="icon"
                className={cn(
                  'h-9 w-9 border-primary/50',
                  !isConnected || isAutoTracking ? 'opacity-50' : 'hover:bg-primary/20 hover:border-primary'
                )}
              >
                <ArrowDownLeft className="w-4 h-4" />
              </Button>
              
              <Button
                onClick={() => handleControl('down')}
                disabled={!isConnected || isAutoTracking}
                variant="outline"
                size="icon"
                className={cn(
                  'h-10 w-10 border-primary/50',
                  !isConnected || isAutoTracking ? 'opacity-50' : 'hover:bg-primary/20 hover:border-primary'
                )}
              >
                <ChevronDown className="w-5 h-5" />
              </Button>
              
              <Button
                onClick={() => handleControl('right-down')}
                disabled={!isConnected || isAutoTracking}
                variant="outline"
                size="icon"
                className={cn(
                  'h-9 w-9 border-primary/50',
                  !isConnected || isAutoTracking ? 'opacity-50' : 'hover:bg-primary/20 hover:border-primary'
                )}
              >
                <ArrowDownRight className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Azimuth & Pitch Values */}
          {ptuState && (
            <div className="pt-2 border-t border-border/50">
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-muted/20 p-2 rounded border border-border/50">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{t('ptu.azimuth')}</div>
                  <div className="font-mono text-lg font-bold text-tactical-cyan">
                    {ptuState.panActual.toFixed(2)}°
                  </div>
                </div>
                <div className="bg-muted/20 p-2 rounded border border-border/50">
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">{t('ptu.pitch')}</div>
                  <div className="font-mono text-lg font-bold text-tactical-cyan">
                    {ptuState.tiltActual.toFixed(2)}°
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </DataPanel>
  );
}
