import { useEffect, useState } from 'react';

type HealthResponse = {
  status: string;
  timestamp: string;
};

type HealthState =
  | { state: 'loading' }
  | { state: 'ok'; payload: HealthResponse }
  | { state: 'error'; message: string };

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
  return (
    <div className="app">
      <header className="topbar">
        <h1>GIS Agent Workspace (POC)</h1>
        <HealthBadge />
      </header>

      <main className="layout">
        <aside className="panel left">
          <h2>Layer Panel</h2>
          <p>Input and output layers will be listed here.</p>
        </aside>

        <section className="panel center">
          <h2>Map Pane</h2>
          <p>MapLibre map integration will be added in the next work items.</p>
        </section>

        <aside className="panel right">
          <h2>Chat Pane</h2>
          <p>assistant-ui chat integration will be added in later work items.</p>
        </aside>
      </main>
    </div>
  );
}
