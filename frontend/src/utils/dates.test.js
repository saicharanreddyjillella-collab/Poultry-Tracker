/* global process */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { localISO, todayISO, monthStartISO } from './dates';

const ORIGINAL_TZ = process.env.TZ;
afterEach(() => { vi.useRealTimers(); process.env.TZ = ORIGINAL_TZ; });

describe('dates in the local (India) time zone', () => {
  it('1:30 AM in India is still today, not yesterday (BUG-021)', () => {
    process.env.TZ = 'Asia/Kolkata';
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-17T20:00:00Z'));      // 01:30 IST on 18 Nov
    expect(new Date().toISOString().slice(0, 10)).toBe('2026-11-17');   // the old, wrong way
    expect(todayISO()).toBe('2026-11-18');
    expect(monthStartISO()).toBe('2026-11-01');
  });

  it('1 Dec at 2 AM: month start is 1 Dec, not 30 Nov', () => {
    process.env.TZ = 'Asia/Kolkata';
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-30T20:30:00Z'));      // 02:00 IST on 1 Dec
    expect(monthStartISO()).toBe('2026-12-01');
  });

  it('formats any date with zero padding', () => {
    expect(localISO(new Date(2026, 0, 5))).toBe('2026-01-05');
  });
});
