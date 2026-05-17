import { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl, { Map as MapLibreMap } from 'maplibre-gl';

type HealthResponse = {
  status: string;
  timestamp: string;
};

type HealthState =
  | { state: 'loading' }
  | { state: 'ok'; payload: HealthResponse }
  | { state: 'error'; message: string };

type LayerSource = {
  type: string;
  url?: string;
  tiles?: string[];
};

type LayerStyle = {
  preset?: string;
  paint?: Record<string, unknown>;
  layout?: Record<string, unknown>;
};

type LayerDescriptor = {
  id: string;
  name: string;
  kind: 'geojson' | 'vector' | 'raster' | 'cog' | 'wms';
  source: LayerSource;
  style: LayerStyle;
  visible: boolean;
  origin: 'input' | 'agent_output';
};

function HealthBadge() {
  const [health, setHealth] = useState<HealthState>({ state: 'loading' });

  useEffect(() => {
    let mounted = true;

    async function fetchHealth() {
      try {
        const response = await fetch('/api/health');
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = (await response.json()) as HealthResponse;
        if (mounted) {
          setHealth({ state: 'ok', payload });
        }
      } catch (error) {
        if (mounted) {
          const message = error instanceof Error ? error.message : 'Unknown error';
          setHealth({ state: 'error', message });
        }
      }
    }

    fetchHealth();
    return () => {
      mounted = false;
    };
  }, []);

  if (health.state === 'loading') {
    return <span className="health loading">Backend: checking...</span>;
  }
  if (health.state === 'error') {
    return <span className="health error">Backend: offline ({health.message})</span>;
  }
  return (
    <span className="health ok">
      Backend: {health.payload.status} ({health.payload.timestamp})
    </span>
  );
}

export function App() {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [layers, setLayers] = useState<LayerDescriptor[]>([]);
  const [layerLoading, setLayerLoading] = useState<boolean>(true);
  const [layerError, setLayerError] = useState<string | null>(null);

  useEffect(() => {
    async function bootstrapSession() {
      setLayerError(null);
      try {
        const response = await fetch('/api/sessions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        });
        if (!response.ok) {
          throw new Error(`Unable to create session: HTTP ${response.status}`);
        }
        const payload = (await response.json()) as { sessionId: string };
        setSessionId(payload.sessionId);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown session error';
        setLayerError(message);
        setLayerLoading(false);
      }
    }

    bootstrapSession();
  }, []);

  useEffect(() => {
    if (!sessionId) return;

    async function loadLayers() {
      setLayerLoading(true);
      setLayerError(null);
      try {
        const response = await fetch(`/api/sessions/${sessionId}/layers`);
        if (!response.ok) {
          throw new Error(`Unable to fetch layers: HTTP ${response.status}`);
        }
        const payload = (await response.json()) as { layers: LayerDescriptor[] };
        setLayers(payload.layers);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unknown layer load error';
        setLayerError(message);
      } finally {
        setLayerLoading(false);
      }
    }

    loadLayers();
  }, [sessionId]);

  useEffect(() => {
    if (mapRef.current || !mapContainerRef.current) {
      return;
    }

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: 'https://tiles.openfreemap.org/styles/liberty',
      center: [100.5, 13.75],
      zoom: 4,
    });

    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), 'top-right');

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const applyLayers = () => {
      const existingLayerIds = new Set(map.getStyle().layers?.map((layer) => layer.id) ?? []);
      const existingSourceIds = new Set(Object.keys(map.getStyle().sources ?? {}));

      for (const layer of layers) {
        const sourceId = `src_${layer.id}`;
        const layerId = `lyr_${layer.id}`;

        if (!existingSourceIds.has(sourceId)) {
          if (layer.source.type === 'geojson' && layer.source.url) {
            map.addSource(sourceId, { type: 'geojson', data: layer.source.url });
          } else if (layer.source.type === 'raster' && layer.source.tiles) {
            map.addSource(sourceId, { type: 'raster', tiles: layer.source.tiles, tileSize: 256 });
          }
        }

        if (!map.getSource(sourceId)) {
          continue;
        }

        if (!existingLayerIds.has(layerId)) {
          if (layer.kind === 'raster') {
            map.addLayer({
              id: layerId,
              type: 'raster',
              source: sourceId,
              layout: {
                visibility: layer.visible ? 'visible' : 'none',
              },
            });
          } else {
            map.addLayer({
              id: layerId,
              type: 'line',
              source: sourceId,
              paint: {
                'line-color': '#d62828',
                'line-width': 2,
              },
              layout: {
                visibility: layer.visible ? 'visible' : 'none',
              },
            });
          }
        } else {
          map.setLayoutProperty(layerId, 'visibility', layer.visible ? 'visible' : 'none');
        }
      }
    };

    if (map.isStyleLoaded()) {
      applyLayers();
    } else {
      map.once('load', applyLayers);
    }
  }, [layers]);

  const inputLayers = useMemo(() => layers.filter((layer) => layer.origin === 'input'), [layers]);
  const outputLayers = useMemo(
    () => layers.filter((layer) => layer.origin === 'agent_output'),
    [layers]
  );

  async function toggleLayer(layerId: string, nextVisible: boolean) {
    setLayerError(null);
    try {
      const response = await fetch(`/api/layers/${layerId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ visible: nextVisible }),
      });
      if (!response.ok) {
        throw new Error(`Patch failed: HTTP ${response.status}`);
      }

      setLayers((prev) =>
        prev.map((layer) =>
          layer.id === layerId
            ? {
                ...layer,
                visible: nextVisible,
              }
            : layer
        )
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown patch error';
      setLayerError(message);
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>GIS Agent Workspace (POC)</h1>
        <HealthBadge />
      </header>

      <main className="layout">
        <aside className="panel left">
          <h2>Layer Panel</h2>
          {sessionId ? <p className="muted">Session: {sessionId}</p> : null}
          {layerLoading ? <p>Loading layers...</p> : null}
          {layerError ? <p className="error-text">{layerError}</p> : null}

          <section>
            <h3>Input Layers</h3>
            <LayerList layers={inputLayers} onToggle={toggleLayer} />
          </section>

          <section>
            <h3>Agent Output Layers</h3>
            <LayerList layers={outputLayers} onToggle={toggleLayer} />
          </section>
        </aside>

        <section className="panel center">
          <h2>Map Pane</h2>
          <div className="map-root" ref={mapContainerRef} />
        </section>

        <aside className="panel right">
          <h2>Chat Pane</h2>
          <p>assistant-ui chat integration will be added in later work items.</p>
        </aside>
      </main>
    </div>
  );
}

type LayerListProps = {
  layers: LayerDescriptor[];
  onToggle: (layerId: string, nextVisible: boolean) => Promise<void>;
};

function LayerList({ layers, onToggle }: LayerListProps) {
  if (layers.length === 0) {
    return <p className="muted">No layers</p>;
  }

  return (
    <ul className="layer-list">
      {layers.map((layer) => (
        <li key={layer.id}>
          <label>
            <input
              type="checkbox"
              checked={layer.visible}
              onChange={(event) => {
                void onToggle(layer.id, event.target.checked);
              }}
            />
            <span>{layer.name}</span>
          </label>
        </li>
      ))}
    </ul>
  );
}
