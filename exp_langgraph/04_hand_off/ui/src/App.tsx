import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
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

type ChatMessage = {
  id: string;
  role: 'user' | 'system';
  text: string;
};

type SseEventPayload = {
  type: string;
  runId: string;
  sessionId: string;
  timestamp: string;
  payload: Record<string, unknown>;
};

type PendingClarification = {
  runId: string;
  interruptId: string;
  question: string;
};

function HealthBadge() {
  const [health, setHealth] = useState<HealthState>({ state: 'loading' });

  // Runs on mount to check backend health once and update badge state.
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

  const [chatInput, setChatInput] = useState<string>('');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatBusy, setChatBusy] = useState<boolean>(false);
  const [pendingClarification, setPendingClarification] = useState<PendingClarification | null>(
    null
  );
  // TODO(PROD): When persistent thread history/long-term memory is introduced,
  // evaluate migrating chat surface to assistant-ui primitives for richer
  // thread navigation, message lifecycle handling, and lower UI maintenance.
  const eventSourceRef = useRef<EventSource | null>(null);

  // Note: these effects are intentionally separate (not merged into one effect)
  // because they have different triggers/lifecycles (mount, session change,
  // layer change) and different cleanup semantics.

  // Runs on mount to create a new backend session and store sessionId in state.
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

  // Runs whenever sessionId changes; fetches all layers for that session.
  useEffect(() => {
    if (!sessionId) return;
    void reloadLayers(sessionId);
  }, [sessionId]);

  // Runs on mount to initialize MapLibre and registers cleanup on unmount.
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

  // Runs whenever `layers` changes; syncs API layer visibility/sources into map.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const applyLayers = () => {
      const existingLayerIds = new Set(map.getStyle().layers?.map((layer) => layer.id) ?? []);
      const existingSourceIds = new Set(Object.keys(map.getStyle().sources ?? {}));

      for (const layer of layers) {
        const sourceId = `src_${layer.id}`;
        const layerId = `lyr_${layer.id}`;
        const pointLayerId = `${layerId}_point`;
        const lineLayerId = `${layerId}_line`;
        const fillLayerId = `${layerId}_fill`;

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

        if (layer.kind === 'raster') {
          if (!existingLayerIds.has(layerId)) {
            map.addLayer({
              id: layerId,
              type: 'raster',
              source: sourceId,
              layout: {
                visibility: layer.visible ? 'visible' : 'none',
              },
            });
          } else {
            map.setLayoutProperty(layerId, 'visibility', layer.visible ? 'visible' : 'none');
          }
        } else {
          if (!existingLayerIds.has(pointLayerId)) {
            map.addLayer({
              id: pointLayerId,
              type: 'circle',
              source: sourceId,
              filter: ['==', ['geometry-type'], 'Point'],
              paint: {
                'circle-color': '#d62828',
                'circle-radius': 5,
                'circle-stroke-color': '#ffffff',
                'circle-stroke-width': 1,
              },
              layout: {
                visibility: layer.visible ? 'visible' : 'none',
              },
            });
          } else {
            map.setLayoutProperty(pointLayerId, 'visibility', layer.visible ? 'visible' : 'none');
          }

          if (!existingLayerIds.has(lineLayerId)) {
            map.addLayer({
              id: lineLayerId,
              type: 'line',
              source: sourceId,
              filter: ['==', ['geometry-type'], 'LineString'],
              paint: {
                'line-color': '#d62828',
                'line-width': 2,
              },
              layout: {
                visibility: layer.visible ? 'visible' : 'none',
              },
            });
          } else {
            map.setLayoutProperty(lineLayerId, 'visibility', layer.visible ? 'visible' : 'none');
          }

          if (!existingLayerIds.has(fillLayerId)) {
            map.addLayer({
              id: fillLayerId,
              type: 'fill',
              source: sourceId,
              filter: ['==', ['geometry-type'], 'Polygon'],
              paint: {
                'fill-color': '#d62828',
                'fill-opacity': 0.25,
                'fill-outline-color': '#9d0208',
              },
              layout: {
                visibility: layer.visible ? 'visible' : 'none',
              },
            });
          } else {
            map.setLayoutProperty(fillLayerId, 'visibility', layer.visible ? 'visible' : 'none');
          }
        }
      }
    };

    if (map.isStyleLoaded()) {
      applyLayers();
    } else {
      map.once('load', applyLayers);
    }
  }, [layers]);

  // Runs on unmount to close open SSE stream.
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  const inputLayers = useMemo(() => layers.filter((layer) => layer.origin === 'input'), [layers]);
  const outputLayers = useMemo(
    () => layers.filter((layer) => layer.origin === 'agent_output'),
    [layers]
  );

  async function reloadLayers(currentSessionId: string) {
    setLayerLoading(true);
    setLayerError(null);
    try {
      const response = await fetch(`/api/sessions/${currentSessionId}/layers`);
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

  async function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sessionId || !chatInput.trim() || chatBusy) return;

    const text = chatInput.trim();
    setChatInput('');
    setChatBusy(true);
    setChatMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', text }]);

    eventSourceRef.current?.close();

    try {
      let runId: string;
      if (pendingClarification) {
        const response = await fetch(`/api/runs/${pendingClarification.runId}/resume`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            interruptId: pendingClarification.interruptId,
            answer: text,
          }),
        });
        if (!response.ok) {
          throw new Error(`Run resume failed: HTTP ${response.status}`);
        }
        runId = pendingClarification.runId;
        setPendingClarification(null);
        setChatMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: 'system', text: `Run resumed: ${runId}` },
        ]);
      } else {
        const response = await fetch(`/api/sessions/${sessionId}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text }),
        });
        if (!response.ok) {
          throw new Error(`Chat start failed: HTTP ${response.status}`);
        }
        const payload = (await response.json()) as { runId: string };
        runId = payload.runId;
        setChatMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: 'system', text: `Run started: ${runId}` },
        ]);
      }

      const es = new EventSource(`/api/runs/${runId}/stream`);
      eventSourceRef.current = es;
      let expectedClose = false;

      const onAnyEvent = async (eventName: string, ev: MessageEvent) => {
        const data = JSON.parse(ev.data) as SseEventPayload;
        if (eventName === 'layer_created') {
          const createdLayerId = data.payload.layerId;
          if (typeof createdLayerId === 'string') {
            try {
              const response = await fetch(`/api/layers/${createdLayerId}`);
              if (response.ok) {
                const createdLayer = (await response.json()) as LayerDescriptor;
                setLayers((prev) => {
                  const existingIdx = prev.findIndex((l) => l.id === createdLayer.id);
                  if (existingIdx >= 0) {
                    const next = [...prev];
                    next[existingIdx] = createdLayer;
                    return next;
                  }
                  return [...prev, createdLayer];
                });
              }
            } catch {
              if (sessionId) {
                await reloadLayers(sessionId);
              }
            }
          } else if (sessionId) {
            await reloadLayers(sessionId);
          }
        }

        if (eventName === 'clarification_required') {
          const interruptId = data.payload.interruptId;
          const question = data.payload.question;
          if (typeof interruptId === 'string' && typeof question === 'string') {
            setPendingClarification({
              runId: data.runId,
              interruptId,
              question,
            });
            setChatMessages((prev) => [
              ...prev,
              { id: crypto.randomUUID(), role: 'system', text: `Clarification needed: ${question}` },
            ]);
          }
          setChatBusy(false);
          expectedClose = true;
          es.close();
          if (eventSourceRef.current === es) {
            eventSourceRef.current = null;
          }
          return;
        }

        setChatMessages((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            role: 'system',
            text: `${eventName}: ${JSON.stringify(data.payload)}`,
          },
        ]);

        if (eventName === 'done' || eventName === 'error') {
          setPendingClarification(null);
          setChatBusy(false);
          expectedClose = true;
          es.close();
          if (eventSourceRef.current === es) {
            eventSourceRef.current = null;
          }
        }
      };

      ['message', 'tool_start', 'tool_end', 'layer_created', 'clarification_required', 'done', 'error'].forEach((name) => {
        es.addEventListener(name, (ev) => {
          void onAnyEvent(name, ev as MessageEvent);
        });
      });

      es.onerror = () => {
        if (expectedClose) {
          return;
        }
        setChatMessages((prev) => [
          ...prev,
          { id: crypto.randomUUID(), role: 'system', text: 'SSE connection error' },
        ]);
        setChatBusy(false);
        es.close();
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown chat error';
      setChatMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'system', text: message }]);
      setChatBusy(false);
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
          {pendingClarification ? (
            <p className="hint-text">Awaiting clarification for run {pendingClarification.runId}</p>
          ) : null}
          <form className="chat-form" onSubmit={submitChat}>
            <input
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              placeholder={pendingClarification ? pendingClarification.question : 'Ask the agent...'}
              disabled={!sessionId || chatBusy}
            />
            <button type="submit" disabled={!sessionId || !chatInput.trim() || chatBusy}>
              {chatBusy ? 'Running...' : 'Send'}
            </button>
          </form>
          <div className="chat-log">
            {chatMessages.length === 0 ? <p className="muted">No messages yet.</p> : null}
            {chatMessages.map((msg) => (
              <div key={msg.id} className={`chat-msg ${msg.role}`}>
                <strong>{msg.role === 'user' ? 'You' : 'System'}:</strong> {msg.text}
              </div>
            ))}
          </div>
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
