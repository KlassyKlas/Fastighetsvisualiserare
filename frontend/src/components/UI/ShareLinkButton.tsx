import { Check, Link2 } from 'lucide-react';
import { useEffect, useState } from 'react';
import { flushUrlSync } from '@/lib/urlSync';

/** Hur länge "Länk kopierad" visas innan knappen återgår till "Dela". */
const COPIED_FEEDBACK_MS = 2000;

/**
 * Kopiera länken till den aktuella vyn. Adressfältet speglar redan
 * storen (lib/urlSync) och kartvyn (Mapbox hash), så länken är
 * `location.href` — efter att den debouncade skrivningen tvingats fram.
 */
export default function ShareLinkButton() {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), COPIED_FEEDBACK_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const copyLink = async () => {
    // Skrivningen till adressfältet är debouncad — utan flush kopieras
    // vyn som den såg ut för upp till 250 ms sedan.
    flushUrlSync();
    const href = window.location.href;
    // Utan urklipps-API (osäkert ursprung, äldre webbläsare) får
    // användaren kopiera själv ur dialogen.
    if (!navigator.clipboard?.writeText) {
      window.prompt('Kopiera länken', href);
      return;
    }
    try {
      await navigator.clipboard.writeText(href);
      setCopied(true);
    } catch {
      // Nekad behörighet — samma utväg.
      window.prompt('Kopiera länken', href);
    }
  };

  // I kopierat läge färgas hela knappen (ikonen ärver) så att bocken och
  // "Länk kopierad" hör ihop — samma gröna ton som övriga positiva lägen.
  return (
    <button
      onClick={copyLink}
      // Fast minsta bredd: "Länk kopierad" är bredare än "Dela" och skulle
      // annars flytta hela den centrerade filterraden i två sekunder.
      className={`flex items-center justify-center gap-2 min-w-[7.5rem] px-3 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap ${
        copied ? 'text-green-300' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50'
      }`}
      title="Kopiera länk till den här vyn"
    >
      {copied ? <Check className="w-3.5 h-3.5" /> : <Link2 className="w-3.5 h-3.5" />}
      {copied ? 'Länk kopierad' : 'Dela'}
    </button>
  );
}
