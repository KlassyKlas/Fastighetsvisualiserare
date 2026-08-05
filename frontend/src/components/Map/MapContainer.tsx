import { useCallback, useMemo, useState } from 'react';
import Map, {
  Source,
  Layer,
  NavigationControl,
  GeolocateControl,
  ScaleControl,
} from 'react-map-gl';
import type { MapLayerMouseEvent } from 'mapbox-gl';
import type { LayerProps } from 'react-map-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

import { MAPBOX_TOKEN, MAP_STYLES, INITIAL_VIEW_STATE } from '@/config/map';
import { useStore } from '@/store/useStore';
import { useInfrastructure, useProperties } from '@/hooks/useData';
import InfrastructureLayer from './layers/InfrastructureLayer';
import PropertyLayer from './layers/PropertyLayer';
import ImpactZoneLayer from './layers/ImpactZoneLayer';
import type { FeatureCollection, Feature } from 'geojson';

const buildings3dLayer: LayerProps = {
  id: 'buildings-3d',
  source: 'composite',
  'source-layer': 'building',
  type: 'fill-extrusion',
  minzoom: 15,
  paint: {
    'fill-extrusion-color': '#1a1a2e',
    'fill-extrusion-height': [
      'interpolate',
      ['linear'],
      ['zoom'],
      15,
      0,
      15.05,
      ['get', 'height'],
    ],
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
  const {
    layers,
    filters,
    mapStyle,
    setSelectedProject,
    setSelectedProperty,
    setSidebarOpen,
  } = useStore();

  const { data: infraData } = useInfrastructure();
  const { data: propData } = useProperties();

  const [cursor, setCursor] = useState('');

  const filteredInfra = useMemo<FeatureCollection>(() => {
    if (!infraData) return { type: 'FeatureCollection', features: [] };

    let features = infraData.features;

    if (filters.statuses.length > 0) {
      features = features.filter((f) =>
        filters.statuses.includes(f.properties?.status),
      );
    }

    if (filters.projectTypes.length > 0) {
      features = features.filter((f) =>
        filters.projectTypes.includes(f.properties?.project_type),
      );
    }

    return { type: 'FeatureCollection', features };
  }, [infraData, filters.statuses, filters.projectTypes]);

  const filteredProps = useMemo<FeatureCollection>(() => {
    if (!propData) return { type: 'FeatureCollection', features: [] };

    let features = propData.features;

    if (filters.municipalities.length > 0) {
      features = features.filter((f) =>
        filters.municipalities.includes(f.properties?.municipality),
      );
    }

    if (filters.minValue != null) {
      features = features.filter(
        (f) => (f.properties?.assessed_value_sek ?? 0) >= filters.minValue!,
      );
    }

    if (filters.maxValue != null) {
      features = features.filter(
        (f) => (f.properties?.assessed_value_sek ?? 0) <= filters.maxValue!,
      );
    }

    return { type: 'FeatureCollection', features };
  }, [propData, filters.municipalities, filters.minValue, filters.maxValue]);

  const interactiveLayerIds = useMemo(() => {
    const ids: string[] = [];
    if (layers.infrastructure) ids.push('infrastructure-circles');
    if (layers.properties) ids.push('property-fills');
    return ids;
  }, [layers.infrastructure, layers.properties]);

  const handleClick = useCallback(
    (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      if (!feature) return;

      setSidebarOpen(true);

      if (feature.layer?.id === 'infrastructure-circles') {
        setSelectedProject(feature as unknown as Feature);
      } else if (feature.layer?.id === 'property-fills') {
        setSelectedProperty(feature as unknown as Feature);
      }
    },
    [setSelectedProject, setSelectedProperty, setSidebarOpen],
  );

  const handleMouseEnter = useCallback(() => {
    setCursor('pointer');
  }, []);

  const handleMouseLeave = useCallback(() => {
    setCursor('');
  }, []);

  if (!MAPBOX_TOKEN) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-slate-900">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 max-w-md text-center">
          <h2 className="text-xl font-semibold text-slate-100 mb-3">
            Mapbox-token saknas
          </h2>
          <p className="text-slate-400 mb-4">
            Skapa en <code className="text-blue-400">.env</code>-fil i
            projektets rot med:
          </p>
          <code className="block bg-slate-900 text-slate-300 p-3 rounded text-sm">
            VITE_MAPBOX_TOKEN=din_token_har
          </code>
          <p className="text-slate-500 text-sm mt-4">
            Skaffa en token gratis pa{' '}
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
      terrain={
        layers.terrain
          ? { source: 'mapbox-dem', exaggeration: 1.5 }
          : undefined
      }
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

      <ImpactZoneLayer data={filteredInfra} visible={layers.impactZones} />
      <PropertyLayer data={filteredProps} visible={layers.properties} />
      <InfrastructureLayer
        data={filteredInfra}
        visible={layers.infrastructure}
      />
    </Map>
  );
}
