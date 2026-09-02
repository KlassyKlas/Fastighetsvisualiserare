import { describe, expect, it } from 'vitest';
import {
  formatArea,
  formatCurrency,
  formatDate,
  formatDateTime,
  formatDistance,
  formatSek,
} from './format';

// Intl med sv-SE använder smalt mellanslag som tusentalsavgränsare —
// normalisera för robusta jämförelser.
function normalize(value: string): string {
  return value.replace(/[\s\u00a0\u202f]/g, ' ');
}

describe('formatSek', () => {
  it('formaterar miljarder som mdkr', () => {
    expect(formatSek(34_000_000_000)).toBe('34,0 mdkr');
  });

  it('formaterar miljoner som mkr', () => {
    expect(formatSek(12_500_000)).toBe('12,5 mkr');
  });

  it('formaterar mindre belopp med tusentalsavgränsare', () => {
    expect(normalize(formatSek(85_000))).toBe('85 000 kr');
  });
});

describe('formatCurrency', () => {
  it('formaterar hela beloppet', () => {
    expect(normalize(formatCurrency(12_500_000))).toBe('12 500 000 kr');
  });
});

describe('formatArea', () => {
  it('formaterar kvadratmeter', () => {
    expect(normalize(formatArea(4500))).toBe('4 500 m²');
  });
});

describe('formatDistance', () => {
  it('visar meter under en kilometer', () => {
    expect(normalize(formatDistance(432.7))).toBe('433 m');
  });

  it('visar kilometer med decimal över tusen meter', () => {
    expect(formatDistance(2500)).toBe('2,5 km');
  });
});

describe('formatDate', () => {
  it('formaterar ISO-datum på svenska', () => {
    expect(formatDate('2026-08-05')).toBe('5 augusti 2026');
  });

  it('hanterar null och undefined', () => {
    expect(formatDate(null)).toBe('Ej angivet');
    expect(formatDate(undefined)).toBe('Ej angivet');
  });

  it('returnerar rå sträng vid ogiltigt datum', () => {
    expect(formatDate('inte-ett-datum')).toBe('inte-ett-datum');
  });
});

describe('formatDateTime', () => {
  it('formaterar datum och tid på svenska', () => {
    const value = formatDateTime('2026-08-05T12:30:00Z');
    expect(value).toContain('2026');
    expect(value).toMatch(/\d{2}[.:]\d{2}/);
  });

  it('null för saknad eller ogiltig tid', () => {
    expect(formatDateTime(null)).toBeNull();
    expect(formatDateTime(undefined)).toBeNull();
    expect(formatDateTime('inte-en-tid')).toBeNull();
  });
});
