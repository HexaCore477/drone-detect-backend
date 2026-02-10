import { useState, useEffect } from 'react';
import type { OperationalTelemetry, OperationMode } from '@/types/telemetry';

const generateInitialTelemetry = (): OperationalTelemetry => ({
  drone: {
    speed: 45.2,
    distance: 1250,
    attitude: { roll: 2.5, pitch: -1.2, yaw: 127.8 },
    type: 'multirotor',
  },
  laser: {
    enabled: true,
    power: 85,
    frequency: 20,
    lockStatus: 'locked',
  },
  cooling: {
    enabled: true,
    currentTemp: 42.3,
    thresholdTemp: 65.0,
    pumpRunning: true,
  },
  battery: {
    totalCapacity: 12.5,
    currentPercent: 78,
    estimatedChargeTime: 0,
    isCharging: false,
  },
  operationMode: 'human-in-the-loop' as OperationMode,
  environment: {
    temperature: 22.4,
    airPressure: 1013.25,
    humidity: 65,
    windSpeed: 3.2,
    windDirection: 225,
    weatherCondition: 'clear',
  },
  platform: {
    attitude: { roll: 0.3, pitch: -0.1, yaw: 45.0 },
    geoPosition: {
      latitude: 52.5200,
      longitude: 13.4050,
      altitude: 125,
    },
  },
});

export function useOperationalTelemetry() {
  const [telemetry, setTelemetry] = useState<OperationalTelemetry>(generateInitialTelemetry);

  // Static telemetry - no random updates
  useEffect(() => {
    setTelemetry(generateInitialTelemetry());
  }, []);

  const setOperationMode = (mode: OperationMode) => {
    setTelemetry(prev => ({ ...prev, operationMode: mode }));
  };

  const toggleLaser = () => {
    setTelemetry(prev => ({
      ...prev,
      laser: { ...prev.laser, enabled: !prev.laser.enabled },
    }));
  };

  const toggleCooling = () => {
    setTelemetry(prev => ({
      ...prev,
      cooling: { ...prev.cooling, enabled: !prev.cooling.enabled, pumpRunning: !prev.cooling.enabled },
    }));
  };

  return {
    telemetry,
    setOperationMode,
    toggleLaser,
    toggleCooling,
  };
}
