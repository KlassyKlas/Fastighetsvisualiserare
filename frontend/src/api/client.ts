import createClient from 'openapi-fetch';
import type { paths } from '@/api/schema';

/**
 * Tom sträng som standard = relativa anrop. I utveckling proxar Vite
 * /api till backend (se vite.config.ts); i produktion gör nginx samma sak.
 */
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? '';

/**
 * Typad API-klient: sökvägar, parametrar och svarstyper kontrolleras
 * vid kompilering mot backendens OpenAPI-schema.
 */
export const client = createClient<paths>({ baseUrl: API_BASE_URL });
