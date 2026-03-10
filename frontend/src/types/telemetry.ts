// Drone/Target Telemetry
export interface DroneData {
  speed: number; // m/s
  distance: number; // meters
  attitude: {
    roll: number;
    pitch: number;
    yaw: number;
  };
  type: 'fixed-wing' | 'multirotor' | 'helicopter' | 'unknown';
}

// Laser System Status
export interface LaserStatus {
  enabled: boolean;
  power: number; // 0-100%
  frequency: number; // Hz
  lockStatus: 'searching' | 'acquiring' | 'locked' | 'lost';
}

// Water Cooling Status
export interface CoolingStatus {
  enabled: boolean;
  currentTemp: number; // Celsius
  thresholdTemp: number; // Celsius
  pumpRunning: boolean;
}

// Battery Status
export interface BatteryStatus {
  totalCapacity: number; // kWh
  currentPercent: number; // 0-100%
  estimatedChargeTime: number; // minutes, 0 if not charging
  isCharging: boolean;
}

// Operation Mode
export type OperationMode = 
  | 'human-in-the-loop' 
  | 'human-on-the-loop' 
  | 'human-out-of-the-loop';

// Environment Status
export interface EnvironmentStatus {
  temperature: number; // Celsius
  airPressure: number; // hPa
  humidity: number; // 0-100%
  windSpeed: number; // m/s
  windDirection: number; // degrees 0-359
  weatherCondition: 'clear' | 'fog' | 'rain' | 'snow' | 'overcast';
}

// Platform Status
export interface PlatformStatus {
  attitude: {
    roll: number;
    pitch: number;
    yaw: number;
  };
  geoPosition: {
    latitude: number;
    longitude: number;
    altitude: number; // meters
  };
}

// Combined Operational Telemetry
export interface OperationalTelemetry {
  drone: DroneData;
  laser: LaserStatus;
  cooling: CoolingStatus;
  battery: BatteryStatus;
  operationMode: OperationMode;
  environment: EnvironmentStatus;
  platform: PlatformStatus;
}
