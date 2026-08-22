import { describe, expect, it } from 'vitest';
import { cn } from './utils';

describe('cn', () => {
  it('lets a later tailwind class win over an earlier conflicting one', () => {
    expect(cn('bg-secondary', 'bg-transparent')).toBe('bg-transparent');
  });

  it('keeps classes that do not conflict', () => {
    expect(cn('flex items-center', 'gap-2')).toBe('flex items-center gap-2');
  });

  it('drops falsy values', () => {
    expect(cn('flex', false, undefined, null, 'gap-2')).toBe('flex gap-2');
  });

  it('flattens conditional objects and arrays', () => {
    expect(cn(['flex', { hidden: false, 'sm:flex': true }])).toBe('flex sm:flex');
  });

  it('overrides the rounding of a vendored button so a group can own it', () => {
    expect(cn('rounded-lg', 'rounded-none rounded-e-lg')).toBe('rounded-none rounded-e-lg');
  });
});
