import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { SystemStatus } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface CameraStatePanelProps {
  systemStatus: SystemStatus;
}

export function CameraStatePanel({ systemStatus }: CameraStatePanelProps) {
  const { t } = useTranslation();

  const videoStatus = systemStatus.cameraOnline ? t('status.online') : t('status.offline');

  return (
    <DataPanel
      title={t('systemControl.camera', 'Camera State')}
      status={systemStatus.cameraOnline ? 'stable' : 'warning'}
    >
      <div className="space-y-2 text-sm">
        <DataRow
          label={t('systemControl.camera.zoom', 'Zoom')}
          value="1.0"
          unit="×"
        />
        <DataRow
          label={t('systemControl.camera.focus', 'Focus')}
          value={t('systemControl.camera.auto', 'Auto')}
        />
        <DataRow
          label={t('systemControl.camera.link', 'Video Link')}
          value={videoStatus}
          warning={!systemStatus.cameraOnline}
        />
      </div>
    </DataPanel>
  );
}

