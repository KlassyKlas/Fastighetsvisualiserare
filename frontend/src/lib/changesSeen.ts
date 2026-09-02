/**
 * Tidsankaret "senaste besöket" för panelen Nytt sedan senast. Lagras i
 * localStorage (som demo-bevakningarna) — det är per webbläsare, precis
 * som ett besök är, och kräver ingen inloggning eller backend.
 */
const STORAGE_KEY = 'fastighetsvisualiserare.changesSeenAt';

/** localStorage kan saknas (tester, node) eller kasta (privat läge) —
 * då räknas besöket som det första i stället för att fälla appen. */
export function readChangesSeenAt(): string | null {
  try {
    return globalThis.localStorage?.getItem(STORAGE_KEY) ?? null;
  } catch {
    return null;
  }
}

export function writeChangesSeenAt(iso: string): void {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, iso);
  } catch {
    // Skrivfel (kvot, privat läge) — markören lever kvar i storen tills omladdning.
  }
}
