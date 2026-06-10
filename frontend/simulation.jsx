/**
 * MeliCrowd Live Floor — useSimulation() hook (LIVE ONLY).
 *
 * NÃO contém simulador interno. Conecta apenas no WebSocket real
 * em ws://localhost:8101/ws/agents.
 *
 * Quando WS desconectado, retorna estado vazio + `connectionStatus`
 * para que a UI exiba "Aguardando conexão". Reconecta automaticamente
 * com backoff exponencial (1s → 2s → 4s → ... até 30s).
 *
 * Os controles do header (start/stop/scale/agent count) chamam a API
 * REST em http://localhost:8101 — POST /start, /stop, /scale,
 * /personas/generate. NÃO afetam dados — apenas comandam o backend real.
 */

const WS_URL = window.MELICROWD_WS_URL || 'ws://localhost:8101/ws/agents';
const API_URL = window.MELICROWD_API_URL || 'http://localhost:8101';

/* ── Persona archetypes (espelho do backend live_tracker._PERSONA_ARCHETYPE_BY_INCOME) ── */
const ARCHETYPES = [
  { key: 'bargain_hunter', label: 'Bargain Hunter (D)', color: '#FACC15' },
  { key: 'premium_buyer', label: 'Premium Buyer (A)', color: '#A855F7' },
  { key: 'casual_browser', label: 'Casual Browser (C)', color: '#3B82F6' },
  { key: 'researcher', label: 'Researcher (B)', color: '#22C55E' },
];

/* Seller archetypes (espelho de live_tracker._SELLER_ARCHETYPE_BY_STRATEGY) */
const SELLER_ARCHETYPES = [
  { key: 'seller_idle', label: 'Seller Idle', color: '#F97316' },
  { key: 'aggressive_seller', label: 'Aggressive (preço)', color: '#EF4444' },
  { key: 'standard_seller', label: 'Standard', color: '#F97316' },
  { key: 'premium_seller', label: 'Premium', color: '#A855F7' },
];

/* ── Stations: ids correspondem 1:1 aos node_name do graph.py do backend.
   IMPORTANTE: backend envia `station = node_name` (15 valores possíveis). ── */
const STATIONS = [
  // Row 0: Entry / Decision
  { id: 'waiting_pool', label: 'Waiting Pool', icon: 'Clock', row: 0, isQwen: false },
  { id: 'load_persona', label: 'Load Persona', icon: 'UserRound', row: 0, isQwen: false },
  { id: 'decide_session', label: 'Decide Session', icon: 'Brain', row: 0, isQwen: true },
  { id: 'auth', label: 'Auth', icon: 'KeyRound', row: 0, isQwen: false },
  // Row 1: Navigation
  { id: 'browse_home', label: 'Home', icon: 'Home', row: 1, isQwen: false },
  { id: 'search', label: 'Search', icon: 'Search', row: 1, isQwen: false },
  { id: 'product_list', label: 'Product List', icon: 'List', row: 1, isQwen: false },
  { id: 'product_detail', label: 'Product Detail', icon: 'Package', row: 1, isQwen: false },
  { id: 'evaluate_item', label: 'Evaluate Item', icon: 'Brain', row: 1, isQwen: true },
  // Row 2: Conversion
  { id: 'add_to_cart', label: 'Add to Cart', icon: 'ShoppingCart', row: 2, isQwen: false },
  { id: 'continue_or_checkout', label: 'Continue/Checkout', icon: 'GitFork', row: 2, isQwen: false },
  { id: 'checkout_decision', label: 'Checkout Decision', icon: 'Brain', row: 2, isQwen: true },
  { id: 'pay', label: 'Pay', icon: 'CreditCard', row: 2, isQwen: false },
  { id: 'write_review', label: 'Write Review', icon: 'Star', row: 2, isQwen: false },
  { id: 'abandon', label: 'Abandoned', icon: 'XCircle', row: 2, isQwen: false },
  { id: 'purchased', label: 'Purchased', icon: 'CheckCircle', row: 2, isQwen: false },
  // Row 3: Sellers — inventory mgmt (10 stations)
  { id: 'seller_idle',                label: 'Seller Idle',     icon: 'Clock',        row: 3, isQwen: false, isSeller: true },
  { id: 'seller_login',               label: 'Login',           icon: 'KeyRound',     row: 3, isQwen: false, isSeller: true },
  { id: 'seller_audit',               label: 'Audit',           icon: 'List',         row: 3, isQwen: false, isSeller: true },
  { id: 'seller_check_notifications', label: 'Stock Alerts',    icon: 'AlertTriangle',row: 3, isQwen: false, isSeller: true },
  { id: 'seller_decide',              label: 'Decide Focus',    icon: 'Brain',        row: 3, isQwen: true,  isSeller: true },
  { id: 'seller_restock',             label: 'Restock',         icon: 'Package',      row: 3, isQwen: false, isSeller: true },
  { id: 'seller_suspend',             label: 'Suspend',         icon: 'XCircle',      row: 3, isQwen: false, isSeller: true },
  { id: 'seller_create_product',      label: 'Create Product',  icon: 'Brain',        row: 3, isQwen: true,  isSeller: true },
  { id: 'seller_update_price',        label: 'Update Price',    icon: 'CreditCard',   row: 3, isQwen: false, isSeller: true },
  { id: 'seller_done',                label: 'Done',            icon: 'CheckCircle',  row: 3, isQwen: false, isSeller: true },
];

const INTENTS = ['browse', 'research', 'purchase', 'compare'];

/* ── Empty default state when WS is disconnected ── */
const EMPTY_KPIS = {
  activeAgents: 0,
  sessionsPerMin: 0,
  conversionRate: '0.0',
  cartAbandonmentRate: '0.0',
  avgSessionDuration: '0',
  qwenCallsPerMin: 0,
  p95QwenLatency: '0.0',
  errorsLast5Min: 0,
  // Worker-level KPIs (novos)
  totalWorkers: 0,
  busyWorkers: 0,
  idleWorkers: 0,
  utilization: '0.0',
  stationLoad: {},
  sellerTotalWorkers: 0,
  sellerBusyWorkers: 0,
  sellerSessionsPerMin: 0,
};

/* ── REST helpers (control plane) ── */
async function apiPost(path, params) {
  try {
    const url = new URL(API_URL + path);
    Object.entries(params || {}).forEach(([k, v]) => url.searchParams.set(k, v));
    const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
    return r.ok ? await r.json() : { error: `HTTP ${r.status}` };
  } catch (e) {
    return { error: String(e) };
  }
}

async function apiPostJson(path, body, params) {
  try {
    const url = new URL(API_URL + path);
    Object.entries(params || {}).forEach(([k, v]) => url.searchParams.set(k, v));
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    return r.ok ? await r.json() : { error: `HTTP ${r.status}` };
  } catch (e) {
    return { error: String(e) };
  }
}

/* ── useSimulation Hook (LIVE WS only) ── */
function useSimulation() {
  const [agents, setAgents] = React.useState([]);
  const [events, setEvents] = React.useState([]);
  const [kpis, setKpis] = React.useState(EMPTY_KPIS);
  const [nodeStats, setNodeStats] = React.useState({});
  const [connectionStatus, setConnectionStatus] = React.useState('connecting'); // connecting | open | closed
  const [agentCount, setAgentCount] = React.useState(50);
  const [showTrails, setShowTrails] = React.useState(true);
  const [showLabels, setShowLabels] = React.useState(true);
  const [confettiMode, setConfettiMode] = React.useState(false);
  const [poolRunning, setPoolRunning] = React.useState(false);
  const [sellerCount, setSellerCount] = React.useState(5);
  const [sellerPoolRunning, setSellerPoolRunning] = React.useState(false);

  const wsRef = React.useRef(null);
  const reconnectTimeoutRef = React.useRef(null);
  const reconnectAttemptsRef = React.useRef(0);

  // Connect / reconnect logic
  const connect = React.useCallback(() => {
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      return;
    }
    setConnectionStatus('connecting');
    let ws;
    try {
      ws = new WebSocket(WS_URL);
    } catch (e) {
      console.error('[ws] failed to construct', e);
      scheduleReconnect();
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      console.info('[ws] connected to', WS_URL);
      setConnectionStatus('open');
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = (msg) => {
      try {
        const parsed = JSON.parse(msg.data);
        if (parsed.type === 'snapshot' && parsed.data) {
          const { agents: agentList, events: evList, kpis: kpiData, nodeStats: ns } = parsed.data;
          setAgents(agentList || []);
          setEvents((evList || []).map(e => ({ ...e, timestamp: new Date(e.timestamp) })));
          setKpis(kpiData || EMPTY_KPIS);
          setNodeStats(ns || {});
        }
      } catch (err) {
        console.warn('[ws] bad message', err);
      }
    };

    ws.onerror = (e) => {
      console.warn('[ws] error', e);
    };

    ws.onclose = () => {
      console.info('[ws] closed');
      setConnectionStatus('closed');
      wsRef.current = null;
      scheduleReconnect();
    };
  }, []);

  const scheduleReconnect = React.useCallback(() => {
    if (reconnectTimeoutRef.current) return;
    const attempt = reconnectAttemptsRef.current;
    const delay = Math.min(30_000, 1000 * Math.pow(2, attempt)); // 1s,2s,4s,...,30s
    reconnectAttemptsRef.current = attempt + 1;
    console.info(`[ws] reconnect in ${delay}ms (attempt ${attempt + 1})`);
    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectTimeoutRef.current = null;
      connect();
    }, delay);
  }, [connect]);

  React.useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  // Poll /status every 2s to reflect pool running state in header.
  React.useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const r = await fetch(`${API_URL}/status`);
        if (r.ok && !cancelled) {
          const data = await r.json();
          setPoolRunning(Boolean(data?.pool?.running));
          if (data?.pool?.target_agents > 0) {
            setAgentCount(data.pool.target_agents);
          }
        }
      } catch {
        if (!cancelled) setPoolRunning(false);
      }
    };
    const pollSellers = async () => {
      try {
        const r = await fetch(`${API_URL}/sellers/pool/status`);
        if (r.ok && !cancelled) {
          const data = await r.json();
          setSellerPoolRunning(Boolean(data?.running));
          if (data?.target_workers > 0) setSellerCount(data.target_workers);
        }
      } catch {
        if (!cancelled) setSellerPoolRunning(false);
      }
    };
    tick();
    pollSellers();
    const id = setInterval(() => { tick(); pollSellers(); }, 2000);
    return () => { cancelled = true; clearInterval(id); };
  }, []);

  /* ── Control actions (real REST calls) ── */
  const startPool = React.useCallback(async (agents) => {
    return apiPost('/start', { agents: agents ?? agentCount });
  }, [agentCount]);
  const stopPool = React.useCallback(async () => apiPost('/stop', { graceful: true }), []);
  const scalePool = React.useCallback(async (agents) => apiPost('/scale', { agents }), []);
  const seedPersonas = React.useCallback(async (count) => apiPost('/personas/generate', { count }), []);
  const startSellers = React.useCallback(async (workers) => {
    return apiPost('/sellers/start', { workers: workers ?? sellerCount });
  }, [sellerCount]);
  const stopSellers = React.useCallback(async () => apiPost('/sellers/stop', { graceful: true }), []);
  const scaleSellers = React.useCallback(async (workers) => apiPost('/sellers/scale', { workers }), []);
  const seedSellers = React.useCallback(async (count) => {
    return apiPostJson('/sellers/seed-synthetic', { count });
  }, []);

  return {
    agents,
    stations: STATIONS,
    events,
    kpis,
    nodeStats,
    connectionStatus,
    poolRunning,
    controls: {
      isRunning: poolRunning,
      setIsRunning: async (next) => {
        if (next) await startPool();
        else await stopPool();
      },
      agentCount,
      setAgentCount,
      scalePool,
      seedPersonas,
      sellerCount,
      setSellerCount,
      sellerPoolRunning,
      startSellers,
      stopSellers,
      scaleSellers,
      seedSellers,
      setSellerPoolRunning: async (next) => {
        if (next) await startSellers();
        else await stopSellers();
      },
      // Speed/trails/labels are pure client UI toggles (no backend equivalent)
      speed: 1,
      setSpeed: () => {}, // no-op: real backend speed is real time
      showTrails, setShowTrails,
      showLabels, setShowLabels,
      confettiMode, setConfettiMode,
    },
    archetypes: ARCHETYPES,
    sellerArchetypes: SELLER_ARCHETYPES,
  };
}

// Export to window for cross-file access
Object.assign(window, {
  useSimulation,
  STATIONS,
  ARCHETYPES,
  SELLER_ARCHETYPES,
  INTENTS,
  WS_URL,
  API_URL,
});
