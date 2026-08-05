/**
 * TanStack Query-fabrik för Mapbox Isochrone API. Ligger utanför
 * queries.ts eftersom anropet inte går genom backendens OpenAPI-kontrakt
 * utan direkt till Mapbox med kartans token — fungerar även i demo-läge.
 */
import { keepPreviousData, queryOptions } from '@tanstack/react-query';
import { MAPBOX_TOKEN } from '@/config/map';
import { buildIsochroneUrl, normalizeMinutes } from '@/lib/isochrone';
import type { IsochroneCollection, IsochroneOrigin, IsochroneProfile } from '@/domain';

export function isochroneQuery(
  origin: IsochroneOrigin | null,
  profile: IsochroneProfile,
  minutes: number[],
) {
  const contours = normalizeMinutes(minutes);
  return queryOptions({
    queryKey: [
      'isochrone',
      {
        longitude: origin?.longitude ?? null,
        latitude: origin?.latitude ?? null,
        profile,
        contours,
      },
    ],
    queryFn: async ({ signal }): Promise<IsochroneCollection> => {
      if (!origin) throw new Error('Ingen startpunkt vald.');
      const url = buildIsochroneUrl(origin, profile, contours, MAPBOX_TOKEN);
      const response = await fetch(url, { signal });
      if (!response.ok) {
        // Mapbox svarar med { message: "..." } vid fel — visa det hellre
        // än en naken statuskod.
        const message = await response
          .json()
          .then((body: { message?: string }) => body.message)
          .catch(() => undefined);
        throw new Error(message ?? `Mapbox svarade med HTTP ${response.status}.`);
      }
      return (await response.json()) as IsochroneCollection;
    },
    enabled: origin != null && contours.length > 0 && MAPBOX_TOKEN !== '',
    // Restidszoner ändras inte under en session — cachea länge.
    staleTime: 10 * 60_000,
    // Behåll förra zonerna medan nya hämtas — annars blinkar kartan
    // vid varje profil- eller minutbyte.
    placeholderData: keepPreviousData,
  });
}
