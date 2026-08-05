import { format, parseISO } from 'date-fns';
import { sv } from 'date-fns/locale';

const numberFormat = new Intl.NumberFormat('sv-SE');

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
