export type ScenarioId = 'D2_Z1' | 'D14_Z10' | 'D25_Z15' | 'D50_Z25' | 'D100_Z36';

export type LogLevel = 'info' | 'warning' | 'error' | 'success';

export type BalloonSize = 'large' | 'medium' | 'small';

export interface Scenario {
  id: ScenarioId;
  distance: number;
  zoom: number;
  label: string;
}

export interface PTUState {
  panTarget: number;
  panActual: number;
  tiltTarget: number;
  tiltActual: number;
}

export interface KalmanState {
  enabled: boolean;
  predicting: boolean;
  gatingActive: boolean;
  lastUpdate: number;
}

export interface DetectedBalloon {
  id: string;
  color: 'red' | 'blue' | 'green' | 'yellow' | 'other';
  size: BalloonSize;
  centerX: number;
  centerY: number;
  boundingBox: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  isTarget: boolean;
  // Optional 500ms-ahead prediction in pixel coordinates
  predictedCenterX?: number | null;
  predictedCenterY?: number | null;
  // Detection confidence score
  confidence?: number;
}

export interface LogEntry {
  id: string;
  timestamp: Date;
  level: LogLevel;
  category: 'detection' | 'tracking' | 'ptu' | 'kalman' | 'system';
  message: string;
  data?: Record<string, unknown>;
}

export interface SystemStatus {
  connected: boolean;
  cameraOnline: boolean;
  ptuOnline: boolean;
  trackingActive: boolean;
  latencyMs: number;
}

export interface TrackingConfig {
  deadbandPx: number;
  maxDegPerSec: number;
  maxStepDeg: number;
  latencyS: number;
  useKalman: boolean;
}

export interface LaserStatus {
  on: boolean;
  powerPercent: number;
  frequencyHz: number;
}

export interface WaterCoolingStatus {
  on: boolean;
  currentTempC: number;
  thresholdTempC: number;
}

export interface BatteryStatus {
  totalCapacityKwh: number;
  currentPercent: number;
  estimatedTimeToChargeMinutes: number;
}

export type OperationMode = 'human-in-the-loop' | 'human-on-the-loop' | 'human-out-of-the-loop';

export interface EnvironmentStatus {
  temperatureC: number;
  airPressureHpa: number;
  humidityPercent: number;
  windSpeedMs: number;
  windDirectionDeg: number;
  weatherConditions: string;
}

export interface PlatformStatus {
  attitude: {
    roll: number;
    pitch: number;
    yaw: number;
  };
  geoPosition: string;
  gpsCoordinates: {
    lat: number;
    lon: number;
  };
}

export interface DroneData {
  speed: number;
  distance: number;
  attitude: {
    roll: number;
    pitch: number;
    yaw: number;
  };
  type: string;
}
