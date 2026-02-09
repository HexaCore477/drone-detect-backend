import type {
  LaserStatus,
  WaterCoolingStatus,
  BatteryStatus,
  EnvironmentStatus,
  PlatformStatus,
  OperationMode,
  DroneData,
} from '@/types/tracking';

export const DEFAULT_LASER_STATUS: LaserStatus = {
  on: false,
  powerPercent: 0,
  frequencyHz: 0,
};

export const DEFAULT_WATER_COOLING: WaterCoolingStatus = {
  on: true,
  currentTempC: 28.5,
  thresholdTempC: 45,
};

export const DEFAULT_BATTERY: BatteryStatus = {
  totalCapacityKwh: 25.6,
  currentPercent: 78,
  estimatedTimeToChargeMinutes: 45,
};

export const DEFAULT_OPERATION_MODE: OperationMode = 'human-in-the-loop';

export const DEFAULT_ENVIRONMENT: EnvironmentStatus = {
  temperatureC: 22.3,
  airPressureHpa: 1013.25,
  humidityPercent: 65,
  windSpeedMs: 3.2,
  windDirectionDeg: 180,
  weatherConditions: 'Clear',
};

export const DEFAULT_PLATFORM: PlatformStatus = {
  attitude: { roll: 0.2, pitch: -0.5, yaw: 12.3 },
  geoPosition: 'Station Alpha',
  gpsCoordinates: { lat: 52.52, lon: 13.405 },
};

/** Example drone data when target is acquired (replace with real backend data) */
export const EXAMPLE_DRONE_DATA: DroneData = {
  speed: 12.5,
  distance: 250,
  attitude: { roll: 2.1, pitch: -1.5, yaw: 45 },
  type: 'Quadcopter',
};
