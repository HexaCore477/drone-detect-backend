import { useState } from 'react';
import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
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
  Settings
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface PTUControlProps {
  className?: string;
}

export function PTUControl({ className }: PTUControlProps) {
  const [serialPort, setSerialPort] = useState<string>('COM3');
  const [baudRate, setBaudRate] = useState<string>('9600');
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isAutoTracking, setIsAutoTracking] = useState<boolean>(true);

  // Common serial port names
  const serialPorts = ['COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8'];
  const baudRates = ['9600', '19200', '38400', '57600', '115200'];

  const handleConnect = () => {
    setIsConnected(!isConnected);
    // Here you would implement actual serial port connection logic
  };

  const handleControl = (direction: 'left' | 'right' | 'up' | 'down' | 'pause') => {
    if (!isConnected) return;
    // Here you would implement PTU control commands
    console.log(`PTU Control: ${direction}`);
  };

  return (
    <DataPanel 
      title="PTU CONTROL" 
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
              Serial Port Connection
            </div>
          </div>

          {/* Serial Port Name and Baud Rate - One Line */}
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1.5">
              <Label className="text-[10px] text-muted-foreground uppercase tracking-wider">
                Serial Port
              </Label>
              <Select value={serialPort} onValueChange={setSerialPort} disabled={isConnected}>
                <SelectTrigger className="h-8 text-xs font-mono">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {serialPorts.map((port) => (
                    <SelectItem key={port} value={port} className="font-mono">
                      {port}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-[10px] text-muted-foreground uppercase tracking-wider">
                Baud Rate
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
                Disconnect
              </>
            ) : (
              <>
                <Plug className="w-4 h-4" />
                Connect
              </>
            )}
          </Button>

          {/* Connection Status */}
          <div className="flex items-center justify-between px-2 py-1.5 bg-muted/20 rounded border border-border/50">
            <span className="text-[10px] text-muted-foreground uppercase">Status:</span>
            <div className="flex items-center gap-2">
              <div className={cn(
                'w-2 h-2 rounded-full',
                isConnected ? 'bg-tactical-green shadow-[0_0_8px_hsl(var(--status-stable))]' : 'bg-tactical-amber'
              )} />
              <span className={cn(
                'text-xs font-mono',
                isConnected ? 'text-tactical-green' : 'text-tactical-amber'
              )}>
                {isConnected ? 'CONNECTED' : 'DISCONNECTED'}
              </span>
            </div>
          </div>
        </div>

        {/* Control Section */}
        <div className="space-y-3 pt-2 border-t border-border/50">
          <div className="flex items-center gap-2 pb-2">
            <Settings className="w-4 h-4 text-primary" />
            <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
              Control
            </div>
          </div>

          {/* Auto/Manual Tracking Checkbox */}
          <div className="flex items-center space-x-2 p-2 bg-muted/20 rounded border border-border/50">
            <Checkbox
              id="auto-tracking"
              checked={isAutoTracking}
              onCheckedChange={(checked) => setIsAutoTracking(checked === true)}
              disabled={!isConnected}
              className="border-primary data-[state=checked]:bg-primary"
            />
            <Label
              htmlFor="auto-tracking"
              className="text-xs font-mono cursor-pointer flex-1"
            >
              Automatic Object Tracking
            </Label>
            <span className={cn(
              'text-[10px] font-mono px-2 py-0.5 rounded',
              isAutoTracking 
                ? 'bg-tactical-green/20 text-tactical-green border border-tactical-green/50' 
                : 'bg-tactical-amber/20 text-tactical-amber border border-tactical-amber/50'
            )}>
              {isAutoTracking ? 'AUTO' : 'MANUAL'}
            </span>
          </div>

          {/* Control Buttons */}
          <div className="space-y-2">
            {/* <div className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2">
              Manual Control {!isAutoTracking && '(Active)'}
            </div>
             */}
            {/* Up Button */}
            <div className="flex justify-center">
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
            </div>

            {/* Left, Pause, Right Row */}
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

            {/* Down Button */}
            <div className="flex justify-center">
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
            </div>
          </div>

          {/* Control Info */}
          {/* <div className="p-2 bg-muted/10 rounded border border-border/30">
            <div className="text-[9px] text-muted-foreground font-mono space-y-0.5">
              <div>Mode: {isAutoTracking ? 'AUTO' : 'MANUAL'}</div>
              <div>Port: {serialPort} @ {baudRate} baud</div>
              {!isConnected && (
                <div className="text-tactical-amber">Connect to enable control</div>
              )}
            </div>
          </div> */}
        </div>
      </div>
    </DataPanel>
  );
}
