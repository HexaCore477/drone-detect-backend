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

  // Update balloons periodically
  useEffect(() => {
    const interval = setInterval(() => {
      setBalloons(prev => {
        const newBalloons = generateBalloons();
        
        // Smooth movement of existing balloons
        return newBalloons.map(balloon => {
          const existing = prev.find(b => b.id === balloon.id);
          if (existing) {
            const dx = (Math.random() - 0.5) * 20;
            const dy = (Math.random() - 0.5) * 20;
            return {
              ...balloon,
              centerX: Math.max(50, Math.min(1230, existing.centerX + dx)),
              centerY: Math.max(50, Math.min(670, existing.centerY + dy)),
              boundingBox: {
                ...balloon.boundingBox,
                x: Math.max(0, existing.boundingBox.x + dx),
                y: Math.max(0, existing.boundingBox.y + dy),
              },
            };
          }
          return balloon;
        });
      });
    }, 100);

    return () => clearInterval(interval);
  }, []);

  // Update PTU state based on target
  useEffect(() => {
    const interval = setInterval(() => {
      const target = balloons.find(b => b.isTarget);
      if (target) {
        const errorX = target.centerX - 640;
        const errorY = target.centerY - 360;
        
        setPtuState(prev => ({
          panTarget: (errorX * 0.05),
          panActual: prev.panActual + (prev.panTarget - prev.panActual) * 0.1,
          tiltTarget: (errorY * 0.05),
          tiltActual: prev.tiltActual + (prev.tiltTarget - prev.tiltActual) * 0.1,
        }));
      }
    }, 50);

    return () => clearInterval(interval);
  }, [balloons]);

  // Update Kalman state
  useEffect(() => {
    const interval = setInterval(() => {
      setKalmanState(prev => ({
        ...prev,
        predicting: Math.random() > 0.8,
        gatingActive: Math.random() > 0.9,
        lastUpdate: Date.now(),
      }));
    }, 200);

    return () => clearInterval(interval);
  }, []);

  // Generate random logs
  useEffect(() => {
    const interval = setInterval(() => {
      const categories = Object.keys(logMessages) as LogEntry['category'][];
      const category = categories[Math.floor(Math.random() * categories.length)];
      const messages = logMessages[category];
      let message = messages[Math.floor(Math.random() * messages.length)];
      
      // Replace placeholders with random values
      message = message.replace(/\{\}/g, () => (Math.random() * 100).toFixed(1));
      
      const levels: LogEntry['level'][] = ['info', 'info', 'info', 'success', 'warning'];
      const level = levels[Math.floor(Math.random() * levels.length)];
      
      addLog(category, level, message);
    }, 500);

    return () => clearInterval(interval);
  }, [addLog]);

  // Update system status
  useEffect(() => {
    const interval = setInterval(() => {
      setSystemStatus(prev => ({
        ...prev,
        latencyMs: 40 + Math.floor(Math.random() * 30),
      }));
    }, 1000);

    return () => clearInterval(interval);
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
