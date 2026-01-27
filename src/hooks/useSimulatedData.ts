import { useState, useEffect, useCallback } from 'react';
import type { 
  DetectedBalloon, 
  PTUState, 
  KalmanState, 
  LogEntry, 
  SystemStatus,
  ScenarioId 
} from '@/types/tracking';

// Generate a random ID
const generateId = () => Math.random().toString(36).substring(2, 9);

// Simulate balloon detection
const generateBalloons = (): DetectedBalloon[] => {
  const colors: DetectedBalloon['color'][] = ['red', 'blue', 'green', 'yellow'];
  const sizes: DetectedBalloon['size'][] = ['large', 'medium', 'small'];
  
  const balloons: DetectedBalloon[] = [];
  
  // Always have at least one red balloon
  const redSizes = ['large', 'medium', 'small'] as const;
  redSizes.forEach((size, idx) => {
    if (Math.random() > 0.3) { // 70% chance each red balloon is visible
      const centerX = 400 + Math.random() * 480;
      const centerY = 200 + Math.random() * 320;
      const boxSize = size === 'large' ? 100 : size === 'medium' ? 60 : 35;
      
      balloons.push({
        id: `red-${size}`,
        color: 'red',
        size,
        centerX,
        centerY,
        boundingBox: {
          x: centerX - boxSize / 2,
          y: centerY - boxSize / 2,
          width: boxSize,
          height: boxSize,
        },
        isTarget: idx === 0 && balloons.filter(b => b.color === 'red').length === 0,
      });
    }
  });

  // Add some other colored balloons
  for (let i = 0; i < 3; i++) {
    if (Math.random() > 0.5) {
      const color = colors[Math.floor(Math.random() * colors.length)];
      if (color !== 'red') {
        const size = sizes[Math.floor(Math.random() * sizes.length)];
        const centerX = 100 + Math.random() * 1000;
        const centerY = 100 + Math.random() * 520;
        const boxSize = size === 'large' ? 80 : size === 'medium' ? 50 : 30;
        
        balloons.push({
          id: generateId(),
          color,
          size,
          centerX,
          centerY,
          boundingBox: {
            x: centerX - boxSize / 2,
            y: centerY - boxSize / 2,
            width: boxSize,
            height: boxSize,
          },
          isTarget: false,
        });
      }
    }
  }

  // Mark the largest red as target
  const redBalloons = balloons.filter(b => b.color === 'red');
  if (redBalloons.length > 0) {
    const sizePriority = { large: 0, medium: 1, small: 2 };
    const sorted = redBalloons.sort((a, b) => sizePriority[a.size] - sizePriority[b.size]);
    sorted[0].isTarget = true;
  }

  return balloons;
};

// Simulate log entries
const logMessages = {
  detection: [
    'Red balloon detected at ({}x, {}y)',
    'Target acquired: size={}',
    'Detection confidence: {}%',
    'Frame processed in {}ms',
  ],
  tracking: [
    'Tracking update: error={}px',
    'Target lock maintained',
    'Switching target priority',
    'Deadband check: {}px',
  ],
  ptu: [
    'Pan command: {}°',
    'Tilt command: {}°',
    'Rate limited: {}°/s',
    'Step clamped to {}°',
  ],
  kalman: [
    'State prediction: u={}, v={}',
    'Measurement update received',
    'Gating threshold: {}',
    'Innovation: {} pixels',
  ],
  system: [
    'System heartbeat OK',
    'Scene {} loaded',
    'Configuration updated',
    'Latency measurement: {}ms',
  ],
};

export function useSimulatedData(activeScenario: ScenarioId) {
  const [balloons, setBalloons] = useState<DetectedBalloon[]>([]);
  const [ptuState, setPtuState] = useState<PTUState>({
    panTarget: 0,
    panActual: 0,
    tiltTarget: 0,
    tiltActual: 0,
  });
  const [kalmanState, setKalmanState] = useState<KalmanState>({
    enabled: true,
    predicting: false,
    gatingActive: false,
    lastUpdate: Date.now(),
  });
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [systemStatus, setSystemStatus] = useState<SystemStatus>({
    connected: true,
    cameraOnline: true,
    ptuOnline: true,
    trackingActive: true,
    latencyMs: 45,
  });

  const addLog = useCallback((
    category: LogEntry['category'], 
    level: LogEntry['level'], 
    message: string
  ) => {
    setLogs(prev => {
      const newLogs = [...prev, {
        id: generateId(),
        timestamp: new Date(),
        level,
        category,
        message,
      }];
      // Keep only last 100 logs
      return newLogs.slice(-100);
    });
  }, []);

  // Initialize balloons once (no random updates)
  useEffect(() => {
    setBalloons(generateBalloons());
  }, []);

  // Initialize PTU state (no random updates)
  useEffect(() => {
    const target = balloons.find(b => b.isTarget);
    if (target) {
      const errorX = target.centerX - 640;
      const errorY = target.centerY - 360;
      
      setPtuState({
        panTarget: errorX * 0.05,
        panActual: errorX * 0.05,
        tiltTarget: errorY * 0.05,
        tiltActual: errorY * 0.05,
      });
    }
  }, [balloons]);

  // Initialize Kalman state (no random updates)
  useEffect(() => {
    setKalmanState({
      enabled: true,
      predicting: false,
      gatingActive: false,
      lastUpdate: Date.now(),
    });
  }, []);

  // Initialize logs (no random log generation)
  useEffect(() => {
    // Add initial log entries only
    addLog('system', 'success', 'System initialized');
    addLog('detection', 'info', 'Detection system ready');
  }, [addLog]);

  // Initialize system status (no random updates)
  useEffect(() => {
    setSystemStatus({
      connected: true,
      cameraOnline: true,
      ptuOnline: true,
      trackingActive: true,
      latencyMs: 55,
    });
  }, []);

  return {
    balloons,
    ptuState,
    kalmanState,
    logs,
    systemStatus,
    addLog,
  };
}
