import { useQuery } from '@tanstack/react-query';
import type { Geometry } from 'geojson';
import { useEffect, useState } from 'react';
import { detailPlanQuery, projectQuery, propertyQuery } from '@/api/queries';
import { MAP_HASH_NAME } from '@/config/map';
import { focusGeometry } from '@/lib/mapBridge';
import { DEFAULT_URL_STATE } from '@/lib/urlState';
import { useUiStore } from '@/store/uiStore';

/**
 * Gemensam upplösning: när objektet hämtats väljs det, fliken återställs
 * och kartan zoomas dit; misslyckas hämtningen släpps valet. Med ett
 * cachelagrat svar finns data redan vid monteringen och StrictMode kör
 * då effekten två gånger — ofarligt, eftersom setSelectedX och
 * focusGeometry är idempotenta (samma objekt, samma rektangel).
 */
function useResolveSelection<TFeature extends { geometry: Geometry | null }>(
  data: TFeature | undefined,
  isError: boolean,
  select: (feature: TFeature) => void,
  focus: boolean,
): void {
  const setPendingSelection = useUiStore((s) => s.setPendingSelection);
  const setSidebarTab = useUiStore((s) => s.setSidebarTab);

  useEffect(() => {
    if (data) {
      // setSelectedX öppnar alltid detaljfliken, men en flik som länken
      // angav (eller som användaren hunnit klicka på under hämtningen)
      // ska vinna — den läses därför av innan valet görs.
      const tab = useUiStore.getState().sidebarTab;
      select(data);
      if (tab !== 'details') setSidebarTab(tab);
      if (focus) focusGeometry(data.geometry);
      setPendingSelection(null);
    } else if (isError) {
      // En död länk (okänt id, annan miljö, saknas i demodatat) är inget
      // backendfel: ErrorBanner täcker kartans dataströmmar, och att flagga
      // här skulle få en gammal länk att se ut som ett avbrott. Valet
      // släpps tyst och appen öppnar i övrigt som länken anger.
      // Detaljfliken öppnades för valet (parseUrlState) — utan objekt är
      // den tom, så den lämnas för standardfliken precis som tolkningen gör
      // för `flik=details` utan val. Har användaren hunnit välja något
      // annat, eller byta flik, under hämtningen rörs inget.
      const s = useUiStore.getState();
      if (
        s.sidebarTab === 'details' &&
        !s.selectedProject &&
        !s.selectedProperty &&
        !s.selectedDetailPlan
      ) {
        setSidebarTab(DEFAULT_URL_STATE.sidebarTab);
      }
      setPendingSelection(null);
    }
  }, [data, isError, select, focus, setPendingSelection, setSidebarTab]);
}

function PropertyLoader({ id, focus }: { id: number; focus: boolean }) {
  const { data, isError } = useQuery(propertyQuery(id));
  const setSelectedProperty = useUiStore((s) => s.setSelectedProperty);
  useResolveSelection(data, isError, setSelectedProperty, focus);
  return null;
}

function ProjectLoader({ id, focus }: { id: number; focus: boolean }) {
  const { data, isError } = useQuery(projectQuery(id));
  const setSelectedProject = useUiStore((s) => s.setSelectedProject);
  useResolveSelection(data, isError, setSelectedProject, focus);
  return null;
}

function DetailPlanLoader({ id, focus }: { id: number; focus: boolean }) {
  const { data, isError } = useQuery(detailPlanQuery(id));
  const setSelectedDetailPlan = useUiStore((s) => s.setSelectedDetailPlan);
  useResolveSelection(data, isError, setSelectedDetailPlan, focus);
  return null;
}

/**
 * Löser upp valet ur en öppnad länk (`fastighet=`/`projekt=`/`detaljplan=`,
 * lagt i storen som pendingSelection av lib/urlSync): hämtar objektet med
 * full geometri (bättre än kartklickets feature), öppnar detaljpanelen och
 * zoomar kartan dit. Renderar ingenting.
 */
export default function UrlSelectionLoader() {
  const pending = useUiStore((s) => s.pendingSelection);

  // Fanns en kartvy i länken ska den gälla — då zoomas inte till objektet.
  // Läses under första renderingen, som sker före alla effekter och därmed
  // innan Mapbox (skapad i en effekt) hunnit skriva sin egen hash. Det är
  // en ögonblicksbild per sidladdning: ett senare popstate till en post
  // med både annat val och egen hash (kräver manuell hashredigering, appen
  // gör aldrig pushState) zoomar därför till objektet — accepterat kantfall.
  const [hadMapHash] = useState(() => window.location.hash.includes(`${MAP_HASH_NAME}=`));

  if (!pending) return null;

  switch (pending.kind) {
    case 'property':
      return <PropertyLoader key={pending.id} id={pending.id} focus={!hadMapHash} />;
    case 'project':
      return <ProjectLoader key={pending.id} id={pending.id} focus={!hadMapHash} />;
    case 'detailPlan':
      return <DetailPlanLoader key={pending.id} id={pending.id} focus={!hadMapHash} />;
  }
}
