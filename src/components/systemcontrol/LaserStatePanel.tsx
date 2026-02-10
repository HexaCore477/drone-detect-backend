import { useState } from 'react';
import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { LaserStatus, WaterCoolingStatus } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface LaserStatePanelProps {
  laserStatus: LaserStatus;
  coolingStatus: WaterCoolingStatus;
}

export function LaserStatePanel({ laserStatus, coolingStatus }: LaserStatePanelProps) {
  const { t } = useTranslation();

  const [enabled, setEnabled] = useState(laserStatus.on);
  const [interlockOk, setInterlockOk] = useState(true);
  const [alarm, setAlarm] = useState(false);

  return (
    <DataPanel
      title={t('systemControl.laserState', 'Laser State')}
      status={enabled ? 'stable' : 'warning'}
    >
      <div className="space-y-2 text-sm">
        <DataRow
          label={t('systemControl.laser.enabled', 'Enabled')}
          value={enabled ? t('camera.on') : t('camera.off')}
        />
        <button
          type="button"
          className="w-full text-right text-[11px] text-muted-foreground hover:text-primary"
          onClick={() => setEnabled((v) => !v)}
        >
          {enabled ? t('systemControl.switchOff', 'Set OFF') : t('systemControl.switchOn', 'Set ON')}
        </button>

        <DataRow
          label={t('systemControl.laser.interlock', 'Interlock')}
          value={interlockOk ? t('systemControl.ok', 'OK') : t('systemControl.open', 'Open')}
        />
        <button
          type="button"
          className="w-full text-right text-[11px] text-muted-foreground hover:text-primary"
          onClick={() => setInterlockOk((v) => !v)}
        >
          {interlockOk ? t('systemControl.setOpen', 'Set Open') : t('systemControl.setOk', 'Set OK')}
        </button>

        {/* Temperature is read-only, from coolingStatus */}
        <DataRow
          label={t('systemControl.laser.temp', 'Temperature')}
          value={coolingStatus.currentTempC.toFixed(1)}
          unit="°C"
        />

        <DataRow
          label={t('systemControl.laser.alarms', 'Alarms')}
          value={alarm ? t('systemControl.yes', 'Yes') : t('systemControl.no', 'No')}
          warning={alarm}
        />
        <button
          type="button"
          className="w-full text-right text-[11px] text-muted-foreground hover:text-primary"
          onClick={() => setAlarm((v) => !v)}
        >
          {alarm ? t('systemControl.clearAlarm', 'Clear Alarm') : t('systemControl.raiseAlarm', 'Raise Alarm')}
        </button>
      </div>
    </DataPanel>
  );
}

