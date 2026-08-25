import { useQuery } from '@tanstack/react-query';
import type { Map as MapboxMap, MapLayerMouseEvent } from 'mapbox-gl';
import { useCallback, useMemo, useState } from 'react';
import Map, {
  GeolocateControl,
  Layer,
  NavigationControl,
  ScaleControl,
  Source,
} from 'react-map-gl/mapbox';
import type { LayerProps } from 'react-map-gl/mapbox';

import { isochroneQuery } from '@/api/isochrone';
import {
  desoAreasQuery,
  detailPlansQuery,
  impactZonesQuery,
  projectsQuery,
  propertiesQuery,
  proximityScoresQuery,
  watchesQuery,
} from '@/api/queries';
import { INITIAL_VIEW_STATE, MAP_STYLES, MAPBOX_TOKEN } from '@/config/map';
import type { DetailPlanFeature, ProjectFeature, PropertyFeature } from '@/domain';
import { useUiStore } from '@/store/uiStore';
import DesoLayer from './layers/DesoLayer';
import DetailPlanLayer from './layers/DetailPlanLayer';
import ImpactZoneLayer from './layers/ImpactZoneLayer';
import InfrastructureLayer from './layers/InfrastructureLayer';
import IsochroneLayer from './layers/IsochroneLayer';
import PropertyLayer from './layers/PropertyLayer';
import WatchLayer, { WatchDraftLayer } from './layers/WatchLayer';

const buildings3dLayer: LayerProps = {
  id: 'buildings-3d',
  source: 'composite',
  'source-layer': 'building',
  type: 'fill-extrusion',
  minzoom: 15,
  paint: {
    'fill-extrusion-color': '#1a1a2e',
    'fill-extrusion-height': ['interpolate', ['linear'], ['zoom'], 15, 0, 15.05, ['get', 'height']],
    'fill-extrusion-base': [
      'interpolate',
      ['linear'],
      ['zoom'],
      15,
      0,
      15.05,
      ['get', 'min_height'],
    ],
    'fill-extrusion-opacity': 0.7,
  },
};

export default function MapContainer() {
  const layers = useUiStore((s) => s.layers);
  const filters = useUiStore((s) => s.filters);
  const mapStyle = useUiStore((s) => s.mapStyle);
  const setSelectedProject = useUiStore((s) => s.setSelectedProject);
  const setSelectedProperty = useUiStore((s) => s.setSelectedProperty);
  const setSelectedDetailPlan = useUiStore((s) => s.setSelectedDetailPlan);
  const demographicsMetric = useUiStore((s) => s.demographicsMetric);
  const setSidebarOpen = useUiStore((s) => s.setSidebarOpen);

  const scoreColoring = useUiStore((s) => s.scoreColoring);

  const isochroneOrigin = useUiStore((s) => s.isochroneOrigin);
  const isochroneProfile = useUiStore((s) => s.isochroneProfile);
  const isochroneMinutes = useUiStore((s) => s.isochroneMinutes);
  const isochronePicking = useUiStore((s) => s.isochronePicking);
  const setIsochroneOrigin = useUiStore((s) => s.setIsochroneOrigin);

  const watchDrawing = useUiStore((s) => s.watchDrawing);
  const watchDraftPoints = useUiStore((s) => s.watchDraftPoints);
  const addWatchDraftPoint = useUiStore((s) => s.addWatchDraftPoint);

  const { data: projectData } = useQuery(projectsQuery(filters));
  const { data: propertyData } = useQuery(propertiesQuery(filters));
  const { data: zoneData } = useQuery(impactZonesQuery(filters));
  const { data: scoreData } = useQuery({
    ...proximityScoresQuery(filters),
    enabled: scoreColoring,
  });
  const { data: isochroneData } = useQuery(
    isochroneQuery(isochroneOrigin, isochroneProfile, isochroneMinutes),
  );
  const { data: watchData } = useQuery(watchesQuery());

  // Detaljplaner och DeSO är nationella datamängder — de hämtas per
  // kartvy (bbox sätts vid load/moveend) och bara när lagret är på.
  const [viewportBbox, setViewportBbox] = useState<string | null>(null);
  const updateViewportBbox = useCallback((map: MapboxMap) => {
    const bounds = map.getBounds();
    if (!bounds) return;
    const clamp = (value: number, limit: number) => Math.max(-limit, Math.min(limit, value));
    const bbox = [
      clamp(bounds.getWest(), 180),
      clamp(bounds.getSouth(), 90),
      clamp(bounds.getEast(), 180),
      clamp(bounds.getNorth(), 90),
    ]
      // 3 decimaler ≈ 100 m — grovt nog att inte skapa nya cacheposter
      // för varje pixelflytt, fint nog för hämtning per vy.
      .map((value) => value.toFixed(3))
      .join(',');
    setViewportBbox(bbox);
  }, []);

  const { data: detailPlanData } = useQuery({
    ...detailPlansQuery(viewportBbox),
    enabled: layers.detailPlans && viewportBbox != null,
  });
  const { data: desoData } = useQuery({
    ...desoAreasQuery(viewportBbox),
    enabled: layers.demographics && viewportBbox != null,
  });

  const [cursor, setCursor] = useState('');

  const useScores = scoreColoring && scoreData != null;
  const maxScore = useMemo(
    () =>
      scoreData && scoreData.features.length > 0
        ? Math.max(...scoreData.features.map((f) => f.properties.score))
        : 1,
    [scoreData],
  );

  // Poängläget berikar fastighetslagret med score i stället för att byta
  // datakälla — annars försvinner fastigheter utan närliggande projekt
  // helt från kartan (poängendpointen inner-joinar mot projekten).
  const enrichedPropertyData = useMemo(() => {
    if (!useScores || !propertyData || !scoreData) return propertyData;
    // OBS: react-map-gl:s Map-komponent skuggar inbyggda Map här —
    // därför ett vanligt uppslagsobjekt.
    const scoreById: Record<number, number> = {};
    for (const feature of scoreData.features) {
      scoreById[feature.properties.id] = feature.properties.score;
    }
    return {
      ...propertyData,
      features: propertyData.features.map((feature) => {
        const score = scoreById[feature.properties.id];
        if (score == null) return feature;
        return { ...feature, properties: { ...feature.properties, score } };
      }),
    } as typeof propertyData;
  }, [useScores, propertyData, scoreData]);

  const interactiveLayerIds = useMemo(() => {
    const ids: string[] = [];
    if (layers.infrastructure) {
      ids.push('infrastructure-circles', 'infrastructure-lines', 'infrastructure-polygons');
    }
    if (layers.properties) {
      ids.push('property-fills');
    }
    if (layers.detailPlans) {
      ids.push('detail-plan-fills');
    }
    return ids;
  }, [layers.infrastructure, layers.properties, layers.detailPlans]);

  const handleClick = useCallback(
    (event: MapLayerMouseEvent) => {
      // I ritläget lägger varje kartklick till ett hörn i bevaknings-
      // området — inga markeringar får ske samtidigt.
      if (watchDrawing) {
        addWatchDraftPoint([event.lngLat.lng, event.lngLat.lat]);
        return;
      }

      // I väljarläget blir nästa kartklick startpunkt för restidsanalysen —
      // och får inte samtidigt markera fastigheten/projektet under muspekaren.
      if (isochronePicking) {
        setIsochroneOrigin({
          longitude: event.lngLat.lng,
          latitude: event.lngLat.lat,
          label: 'Vald punkt på kartan',
        });
        return;
      }

      const feature = event.features?.[0];
      if (!feature) return;

      setSidebarOpen(true);

      const layerId = feature.layer?.id;
      if (
        layerId === 'infrastructure-circles' ||
        layerId === 'infrastructure-lines' ||
        layerId === 'infrastructure-polygons'
      ) {
        setSelectedProject(feature as unknown as ProjectFeature);
      } else if (layerId === 'property-fills') {
        setSelectedProperty(feature as unknown as PropertyFeature);
      } else if (layerId === 'detail-plan-fills') {
        setSelectedDetailPlan(feature as unknown as DetailPlanFeature);
      }
    },
    [
      addWatchDraftPoint,
      isochronePicking,
      setIsochroneOrigin,
      setSelectedDetailPlan,
      setSelectedProject,
      setSelectedProperty,
      setSidebarOpen,
      watchDrawing,
    ],
  );

  const handleMouseEnter = useCallback(() => setCursor('pointer'), []);
  const handleMouseLeave = useCallback(() => setCursor(''), []);

  if (!MAPBOX_TOKEN) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-slate-900">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 max-w-md text-center">
          <h2 className="text-xl font-semibold text-slate-100 mb-3">Mapbox-token saknas</h2>
          <p className="text-slate-400 mb-4">
            Skapa en <code className="text-blue-400">.env</code>-fil i{' '}
            <code className="text-blue-400">frontend/</code> med:
          </p>
          <code className="block bg-slate-900 text-slate-300 p-3 rounded text-sm">
            VITE_MAPBOX_TOKEN=din_token_här
          </code>
          <p className="text-slate-500 text-sm mt-4">
            Skaffa en token gratis på{' '}
            <a
              href="https://mapbox.com"
              target="_blank"
              rel="noreferrer"
              className="text-blue-400 underline"
            >
              mapbox.com
            </a>
          </p>
        </div>
      </div>
    );
  }

  return (
    <Map
      initialViewState={INITIAL_VIEW_STATE}
      mapboxAccessToken={MAPBOX_TOKEN}
      mapStyle={MAP_STYLES[mapStyle]}
      style={{ width: '100%', height: '100%' }}
      terrain={layers.terrain ? { source: 'mapbox-dem', exaggeration: 1.5 } : undefined}
      fog={{
        color: 'rgb(10, 10, 30)',
        'high-color': 'rgb(20, 20, 50)',
        'horizon-blend': 0.08,
        'space-color': 'rgb(5, 5, 20)',
        'star-intensity': 0.6,
      }}
      interactiveLayerIds={interactiveLayerIds}
      onClick={handleClick}
      onLoad={(event) => updateViewportBbox(event.target)}
      onMoveEnd={(event) => updateViewportBbox(event.target)}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      cursor={isochronePicking || watchDrawing ? 'crosshair' : cursor}
    >
      <NavigationControl position="top-right" />
      <GeolocateControl position="top-right" />
      <ScaleControl position="bottom-left" />

      <Source
        id="mapbox-dem"
        type="raster-dem"
        url="mapbox://mapbox.mapbox-terrain-dem-v1"
        tileSize={512}
        maxzoom={14}
      />

      {layers.buildings3d && <Layer {...buildings3dLayer} />}

      {/* Ritordning nedifrån och upp: choropleth → zoner → isokroner →
          detaljplaner → fastigheter → projekt. Klickprioritet följer
          ordningen uppifrån (översta träffade lagret vinner). */}
      {desoData && (
        <DesoLayer data={desoData} visible={layers.demographics} metric={demographicsMetric} />
      )}
      {zoneData && <ImpactZoneLayer data={zoneData} visible={layers.impactZones} />}
      {isochroneOrigin && (
        <IsochroneLayer origin={isochroneOrigin} data={isochroneData} minutes={isochroneMinutes} />
      )}
      {detailPlanData && <DetailPlanLayer data={detailPlanData} visible={layers.detailPlans} />}
      {watchData && <WatchLayer data={watchData} visible={layers.watches} />}
      {watchDrawing && <WatchDraftLayer points={watchDraftPoints} />}
      {enrichedPropertyData && (
        <PropertyLayer
          data={enrichedPropertyData}
          visible={layers.properties}
          colorByScore={useScores}
          maxScore={maxScore}
        />
      )}
      {projectData && <InfrastructureLayer data={projectData} visible={layers.infrastructure} />}
    </Map>
  );
}
