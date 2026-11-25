export type PopulationPoint = readonly [number, number, number];

export interface PopulationRegion {
  readonly id: string;
  readonly minimum: PopulationPoint;
  readonly maximum: PopulationPoint;
  /** Certifies that the entire closed ball around point is in the region. */
  fits(point: PopulationPoint, clearance: number): boolean;
  /** Certifies that a sphere stays in the region along a straight move. */
  fitsSegment?(from: PopulationPoint, to: PopulationPoint, clearance: number): boolean;
}

export interface SpatialPopulationSpec {
  readonly kind: 'molish-spatial-population/1';
  readonly id: string;
  readonly region: string;
  readonly count: number;
  readonly radius: number;
  readonly maxStep: number;
  readonly seed: number;
}

export const POPULATION_STEP_SECONDS = 1 / 30;
export const POPULATION_MOTION_VERSION = 'seeded-swept-sphere/2';

const MAX_POPULATION = 4_096;
const PLACEMENT_ATTEMPTS = 4_096;
const DIRECTION_ATTEMPTS = 32;
const STEP_ATTEMPTS = 8;
const UINT32_MAX = 0xffff_ffff;
const UINT32_RANGE = UINT32_MAX + 1;

function randomStream(seed: number) {
  let state = seed;
  return {
    get state() { return state; },
    next() {
      // Mulberry32 uses exact unsigned integer state and arithmetic.
      state = (state + 0x6d2b79f5) >>> 0;
      let mixed = Math.imul(state ^ (state >>> 15), 1 | state);
      mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), 61 | mixed);
      return ((mixed ^ (mixed >>> 14)) >>> 0) / UINT32_RANGE;
    },
  };
}

function bounds(region: PopulationRegion, radius: number): [PopulationPoint, PopulationPoint] {
  const { minimum, maximum } = region;
  for (let axis = 0; axis < 3; axis++) {
    if (!Number.isFinite(minimum[axis]) || !Number.isFinite(maximum[axis])
      || minimum[axis] >= maximum[axis] || !Number.isFinite(maximum[axis] - minimum[axis])) {
      throw new RangeError('Spatial population region bounds must be finite and increasing.');
    }
  }
  const low: PopulationPoint = [minimum[0] + radius, minimum[1] + radius, minimum[2] + radius];
  const high: PopulationPoint = [maximum[0] - radius, maximum[1] - radius, maximum[2] - radius];
  if (low.some((value, axis) => !Number.isFinite(value) || !Number.isFinite(high[axis]) || value > high[axis])) {
    throw new RangeError('Spatial population entities are too large for the region bounds.');
  }
  return [low, high];
}

function randomDisplacement(random: () => number): PopulationPoint {
  for (let attempt = 0; attempt < DIRECTION_ATTEMPTS; attempt++) {
    const x = random() * 2 - 1;
    const y = random() * 2 - 1;
    const z = random() * 2 - 1;
    if (x * x + y * y + z * z <= 1) return [x, y, z];
  }
  return [0, 0, 0];
}

function interpolate(from: PopulationPoint, to: PopulationPoint, fraction: number): PopulationPoint {
  return [
    from[0] + (to[0] - from[0]) * fraction,
    from[1] + (to[1] - from[1]) * fraction,
    from[2] + (to[2] - from[2]) * fraction,
  ];
}

/** Advances one seeded, fixed-tick population within its region. */
export function createSpatialPopulation(spec: SpatialPopulationSpec, region: PopulationRegion) {
  const { kind, id, region: regionId, count, radius, maxStep, seed } = spec;
  if (kind !== 'molish-spatial-population/1' || typeof id !== 'string' || !id.trim()
    || typeof regionId !== 'string' || !regionId.trim() || regionId !== region.id) {
    throw new TypeError('Spatial population declaration must match its region.');
  }
  if (!Number.isInteger(count) || count < 0 || count > MAX_POPULATION) {
    throw new RangeError(`Spatial population count must be an integer from 0 to ${MAX_POPULATION}.`);
  }
  if (!Number.isFinite(radius) || radius <= 0 || !Number.isFinite(maxStep) || maxStep <= 0) {
    throw new RangeError('Spatial population radius and maximum step must be positive and finite.');
  }
  if (!Number.isInteger(seed) || seed < 0 || seed > UINT32_MAX) {
    throw new RangeError('Spatial population seed must be an unsigned 32-bit integer.');
  }

  let previous: PopulationPoint[];
  let current: PopulationPoint[];
  let randomState = seed;
  let tick = 0;

  function reset() {
    const [low, high] = bounds(region, radius);
    const stream = randomStream(seed);
    const start: PopulationPoint[] = [];
    for (let index = 0; index < count; index++) {
      for (let attempt = 0; attempt < PLACEMENT_ATTEMPTS; attempt++) {
        const candidate: PopulationPoint = [
          low[0] + (high[0] - low[0]) * stream.next(),
          low[1] + (high[1] - low[1]) * stream.next(),
          low[2] + (high[2] - low[2]) * stream.next(),
        ];
        if (region.fits(candidate, radius)) {
          start.push(candidate);
          break;
        }
      }
      if (start.length !== index + 1) {
        throw new RangeError(`Could not place spatial population member ${index} in region "${regionId}".`);
      }
    }
    previous = current = start;
    randomState = stream.state;
    tick = 0;
  }

  function step() {
    const stream = randomStream(randomState);
    const next = current.map(from => {
      const direction = randomDisplacement(stream.next);
      for (let scale = maxStep, attempt = 0; attempt < STEP_ATTEMPTS; attempt++, scale *= 0.5) {
        const to: PopulationPoint = [
          from[0] + direction[0] * scale,
          from[1] + direction[1] * scale,
          from[2] + direction[2] * scale,
        ];
        const distance = Math.hypot(to[0] - from[0], to[1] - from[1], to[2] - from[2]);
        if (distance === 0) return from;
        if (distance > maxStep || !Number.isFinite(distance)) continue;
        if (region.fitsSegment
          ? region.fitsSegment(from, to, radius)
          : Number.isFinite(radius + distance) && region.fits(from, radius + distance)) {
          return to;
        }
      }
      return from;
    });
    previous = current;
    current = next;
    randomState = stream.state;
    tick++;
  }

  function sample(index: number, fraction: number): PopulationPoint {
    if (!Number.isInteger(index) || index < 0 || index >= count) {
      throw new RangeError('Spatial population member index is out of range.');
    }
    if (!Number.isFinite(fraction) || fraction < 0 || fraction > 1) {
      throw new RangeError('Spatial population interpolation fraction must be from 0 to 1.');
    }
    if (fraction === 0) return [...previous[index]];
    if (fraction === 1) return [...current[index]];
    return interpolate(previous[index], current[index], fraction);
  }

  reset();
  return { step, sample, reset, get tick() { return tick; } };
}
