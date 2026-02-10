import { useState } from 'react';
import { DataPanel, DataRow } from '@/components/ui/DataPanel';
import type { WaterCoolingStatus } from '@/types/tracking';
import { useTranslation } from 'react-i18next';

interface CoolingSystemPanelProps {
  coolingStatus: WaterCoolingStatus;
}

export function CoolingSystemPanel({ coolingStatus }: CoolingSystemPanelProps) {
  const { t } = useTranslation();

  const [on, setOn] = useState(coolingStatus.on);
  const [alarm, setAlarm] = useState(false);

  return (
    <DataPanel
      title={t('systemControl.cooling', 'Cooling System')}
      status={on ? 'stable' : 'warning'}
    >
      <div className="space-y-2 text-sm">
        <DataRow
          label={t('systemControl.cooling.onOff', 'On/Off')}
          value={on ? t('camera.on') : t('camera.off')}
        />
        <button
          type="button"
          className="w-full text-right text-[11px] text-muted-foreground hover:text-primary"
          onClick={() => setOn((v) => !v)}
        >
          {on ? t('systemControl.switchOff', 'Set OFF') : t('systemControl.switchOn', 'Set ON')}
        </button>

        {/* Current temp is read-only */}
        <DataRow
          label={t('systemControl.cooling.currentTemp', 'Current Temp')}
          value={coolingStatus.currentTempC.toFixed(1)}
          unit="°C"
        />

        <DataRow
          label={t('systemControl.cooling.alarm', 'Alarm')}
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

