import { useState, useRef } from 'react';
import { DataPanel } from '@/components/ui/DataPanel';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { ZoomIn, ZoomOut } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTranslation } from 'react-i18next';
import { useToast } from '@/hooks/use-toast';
import {
  cameraZoomConnect,
  cameraZoomIn,
  cameraZoomOut,
  cameraZoomStop,
} from '@/api/camera';

interface CameraZoomControlProps {
  className?: string;
}

export function CameraZoomControl({ className }: CameraZoomControlProps) {
  const { t } = useTranslation();
  const { toast } = useToast();
  const [zoomConnected, setZoomConnected] = useState(false);
  const [connectLoading, setConnectLoading] = useState(false);
  const zoomStopRef = useRef<(() => void) | null>(null);

  const handleConnectChange = async (checked: boolean) => {
    if (checked) {
      setConnectLoading(true);
      try {
        await cameraZoomConnect();
        setZoomConnected(true);
        toast({
          variant: 'default',
          title: t('cameraZoom.connected', 'Connected'),
          description: t('cameraZoom.connectedDesc', 'Camera zoom control ready'),
        });
      } catch (e) {
        toast({
          variant: 'destructive',
          title: t('cameraZoom.connectFailed', 'Connect failed'),
          description: e instanceof Error ? e.message : String(e),
        });
      } finally {
        setConnectLoading(false);
      }
    } else {
      try {
        await cameraZoomStop();
      } catch {
        // ignore
      }
      setZoomConnected(false);
    }
  };

  const handleZoomInStart = async () => {
    if (!zoomConnected) return;
    try {
      await cameraZoomIn();
      zoomStopRef.current = () => cameraZoomStop().catch(() => {});
    } catch (e) {
      toast({
        variant: 'destructive',
        title: t('cameraZoom.zoomFailed', 'Zoom failed'),
        description: e instanceof Error ? e.message : String(e),
      });
    }
  };

  const handleZoomOutStart = async () => {
    if (!zoomConnected) return;
    try {
      await cameraZoomOut();
      zoomStopRef.current = () => cameraZoomStop().catch(() => {});
    } catch (e) {
      toast({
        variant: 'destructive',
        title: t('cameraZoom.zoomFailed', 'Zoom failed'),
        description: e instanceof Error ? e.message : String(e),
      });
    }
  };

  const handleZoomEnd = () => {
    if (zoomStopRef.current) {
      zoomStopRef.current();
      zoomStopRef.current = null;
    }
  };

  return (
    <DataPanel
      title={t('cameraZoom.title')}
      className={cn('flex flex-col', className)}
      status={zoomConnected ? 'stable' : 'warning'}
    >
      <div className="space-y-4">
        {/* 1. Camera connect option for zoom control */}
        <div className="flex items-center space-x-2 p-2 bg-muted/20 rounded border border-border/50">
          <Checkbox
            id="camera-zoom-connect"
            checked={zoomConnected}
            onCheckedChange={handleConnectChange}
            disabled={connectLoading}
            className="border-primary data-[state=checked]:bg-primary"
          />
          <Label
            htmlFor="camera-zoom-connect"
            className="text-sm font-medium cursor-pointer flex-1"
          >
            {t('cameraZoom.connectForZoom')}
          </Label>
          <div
            className={cn(
              'w-2 h-2 rounded-full shrink-0',
              zoomConnected ? 'bg-tactical-green' : 'bg-tactical-amber'
            )}
          />
        </div>

        {/* 2. Camera Zoom in - hold to zoom, release to stop */}
        <Button
          type="button"
          variant="outline"
          className="w-full border-primary/50 hover:bg-primary/20 hover:border-primary"
          disabled={!zoomConnected}
          onPointerDown={handleZoomInStart}
          onPointerUp={handleZoomEnd}
          onPointerLeave={handleZoomEnd}
        >
          <ZoomIn className="w-4 h-4 mr-2 shrink-0" />
          {t('cameraZoom.zoomIn')}
        </Button>

        {/* 3. Camera Zoom out - hold to zoom, release to stop */}
        <Button
          type="button"
          variant="outline"
          className="w-full border-primary/50 hover:bg-primary/20 hover:border-primary"
          disabled={!zoomConnected}
          onPointerDown={handleZoomOutStart}
          onPointerUp={handleZoomEnd}
          onPointerLeave={handleZoomEnd}
        >
          <ZoomOut className="w-4 h-4 mr-2 shrink-0" />
          {t('cameraZoom.zoomOut')}
        </Button>
      </div>
    </DataPanel>
  );
}
