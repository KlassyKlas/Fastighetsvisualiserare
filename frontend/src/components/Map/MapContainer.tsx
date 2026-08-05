import { useQuery } from '@tanstack/react-query';
import type { MapLayerMouseEvent } from 'mapbox-gl';
import { useCallback, useMemo, useState } from 'react';
import Map, {
  GeolocateControl,
  Layer,
  NavigationControl,
  ScaleControl,
  Source,
} from 'react-map-gl/mapbox';
import type { LayerProps } from 'react-map-gl/mapbox';

import { impactZonesQuery, projectsQuery, propertiesQuery } from '@/api/queries';
import { INITIAL_VIEW_STATE, MAP_STYLES, MAPBOX_TOKEN } from '@/config/map';
import type { ProjectFeature, PropertyFeature } from '@/domain';
import { useUiStore } from '@/store/uiStore';
import ImpactZoneLayer from './layers/ImpactZoneLayer';
import InfrastructureLayer from './layers/InfrastructureLayer';
import PropertyLayer from './layers/PropertyLayer';

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
  const setSidebarOpen = useUiStore((s) => s.setSidebarOpen);

  const { data: projectData } = useQuery(projectsQuery(filters));
  const { data: propertyData } = useQuery(propertiesQuery(filters));
  const { data: zoneData } = useQuery(impactZonesQuery(filters));

  const [cursor, setCursor] = useState('');

  const interactiveLayerIds = useMemo(() => {
    const ids: string[] = [];
    if (layers.infrastructure) {
      ids.push('infrastructure-circles', 'infrastructure-lines');
    }
    if (layers.properties) {
      ids.push('property-fills');
    }
    return ids;
  }, [layers.infrastructure, layers.properties]);

  const handleClick = useCallback(
    (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      if (!feature) return;

      setSidebarOpen(true);

      const layerId = feature.layer?.id;
      if (layerId === 'infrastructure-circles' || layerId === 'infrastructure-lines') {
        setSelectedProject(feature as unknown as ProjectFeature);
      } else if (layerId === 'property-fills') {
        setSelectedProperty(feature as unknown as PropertyFeature);
      }
    },
    [setSelectedProject, setSelectedProperty, setSidebarOpen],
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
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      cursor={cursor}
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

      {zoneData && <ImpactZoneLayer data={zoneData} visible={layers.impactZones} />}
      {propertyData && <PropertyLayer data={propertyData} visible={layers.properties} />}
      {projectData && <InfrastructureLayer data={projectData} visible={layers.infrastructure} />}
    </Map>
  );
}
