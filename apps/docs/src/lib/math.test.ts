import { describe, expect, it } from 'vitest';
import { clamp } from './math';

describe('clamp', () => {
  it.each([
    [5, 0, 10, 5],
    [-3, 0, 10, 0],
    [42, 0, 10, 10],
    [0, 0, 10, 0],
    [10, 0, 10, 10],
  ])('clamps %s into [%s, %s]', (value, min, max, expected) => {
    expect(clamp(value, min, max)).toBe(expected);
  });

  it('keeps the panel width inside its resize bounds', () => {
    expect(clamp(1200, 320, 600)).toBe(600);
    expect(clamp(120, 320, 600)).toBe(320);
  });
});
