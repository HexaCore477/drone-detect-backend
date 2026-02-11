import { useState } from 'react';
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
  const [zoomInLoading, setZoomInLoading] = useState(false);
  const [zoomOutLoading, setZoomOutLoading] = useState(false);

  const STEP_DURATION_MS = 200;

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

  const handleZoomStep = async (direction: 'in' | 'out') => {
    if (!zoomConnected) return;

    if (direction === 'in') {
      setZoomInLoading(true);
    } else {
      setZoomOutLoading(true);
    }

    try {
      if (direction === 'in') {
        await cameraZoomIn();
      } else {
        await cameraZoomOut();
      }

      // Short continuous pulse, then stop to create a step
      await new Promise((resolve) => setTimeout(resolve, STEP_DURATION_MS));
      await cameraZoomStop();
    } catch (e) {
      toast({
        variant: 'destructive',
        title: t('cameraZoom.zoomFailed', 'Zoom failed'),
        description: e instanceof Error ? e.message : String(e),
      });
    } finally {
      if (direction === 'in') {
        setZoomInLoading(false);
      } else {
        setZoomOutLoading(false);
      }
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

        {/* 2. Camera Zoom in - step by step */}
        <Button
          type="button"
          variant="outline"
          className="w-full border-primary/50 hover:bg-primary/20 hover:border-primary"
          disabled={!zoomConnected || zoomInLoading}
          onClick={() => handleZoomStep('in')}
        >
          {zoomInLoading ? (
            <span className="w-4 h-4 mr-2 shrink-0 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          ) : (
            <ZoomIn className="w-4 h-4 mr-2 shrink-0" />
          )}
          {t('cameraZoom.zoomIn')}
        </Button>

        {/* 3. Camera Zoom out - step by step */}
        <Button
          type="button"
          variant="outline"
          className="w-full border-primary/50 hover:bg-primary/20 hover:border-primary"
          disabled={!zoomConnected || zoomOutLoading}
          onClick={() => handleZoomStep('out')}
        >
          {zoomOutLoading ? (
            <span className="w-4 h-4 mr-2 shrink-0 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          ) : (
            <ZoomOut className="w-4 h-4 mr-2 shrink-0" />
          )}
          {t('cameraZoom.zoomOut')}
        </Button>
      </div>
    </DataPanel>
  );
}
