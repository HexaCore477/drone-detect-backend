import type { Scenario, ScenarioId } from '@/types/tracking';

export const SCENARIOS: Record<ScenarioId, Scenario> = {
  D2_Z1: {
    id: 'D2_Z1',
    distance: 2,
    zoom: 1,
    label: '2m / 1×',
  },
  D14_Z10: {
    id: 'D14_Z10',
    distance: 14,
    zoom: 10,
    label: '14m / 10×',
  },
  D25_Z15: {
    id: 'D25_Z15',
    distance: 25,
    zoom: 15,
    label: '25m / 15×',
  },
  D50_Z25: {
    id: 'D50_Z25',
    distance: 50,
    zoom: 25,
    label: '50m / 25×',
  },
  D100_Z36: {
    id: 'D100_Z36',
    distance: 100,
    zoom: 36,
    label: '100m / 36×',
  },
};

export const SCENARIO_ORDER: ScenarioId[] = ['D2_Z1', 'D14_Z10', 'D25_Z15', 'D50_Z25', 'D100_Z36'];
