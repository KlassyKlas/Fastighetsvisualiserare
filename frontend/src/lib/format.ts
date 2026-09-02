import { format, parseISO } from 'date-fns';
import { sv } from 'date-fns/locale';

const numberFormat = new Intl.NumberFormat('sv-SE');
const dateTimeFormat = new Intl.DateTimeFormat('sv-SE', {
  dateStyle: 'medium',
  timeStyle: 'short',
});

/** Versal först — planstatusar och plantyper kommer gement från Boverkets modell. */
export function capitalizeFirst(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** Tal med svensk tusentalsavgränsare, utan enhet — "12 500". */
export function formatNumber(value: number): string {
  return numberFormat.format(value);
}

/** "34 000 000 000" → "34,0 mdkr"; mindre belopp med tusentalsavgränsare. */
export function formatSek(sek: number): string {
  if (sek >= 1e9) {
    return (sek / 1e9).toFixed(1).replace('.', ',') + ' mdkr';
  }
  if (sek >= 1e6) {
    return (sek / 1e6).toFixed(1).replace('.', ',') + ' mkr';
  }
  return numberFormat.format(sek) + ' kr';
}

export function formatCurrency(sek: number): string {
  return numberFormat.format(sek) + ' kr';
}

export function formatArea(sqm: number): string {
  return numberFormat.format(sqm) + ' m²';
}

export function formatDistance(meters: number): string {
  if (meters >= 1000) {
    return (meters / 1000).toFixed(1).replace('.', ',') + ' km';
  }
  return numberFormat.format(Math.round(meters)) + ' m';
}

/** Andel 0–1 → "68 %". */
export function formatPercent(share: number): string {
  return Math.round(share * 100) + ' %';
}

export function formatDate(dateStr?: string | null): string {
  if (!dateStr) return 'Ej angivet';
  try {
    return format(parseISO(dateStr), 'd MMMM yyyy', { locale: sv });
  } catch {
    return dateStr;
  }
}

/** ISO-tidpunkt → "5 aug. 2026 14:30" (sv-SE); null för saknad/ogiltig tid. */
export function formatDateTime(value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : dateTimeFormat.format(parsed);
}
