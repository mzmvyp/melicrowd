/**
 * MeliCrowd Live Floor — Floor Plan (Stations + Agent Dots)
 */

/* ── Station layout positions ── */
const STATION_LAYOUT = {
  // Row 0 — Entry/Decision (4 stations)
  waiting_pool:    { col: 0, row: 0 },
  load_persona:    { col: 1, row: 0 },
  decide_session:  { col: 2, row: 0 },
  auth:            { col: 3, row: 0 },
  // Row 1 — Navigation (5 stations)
  browse_home:     { col: 0, row: 1 },
  search:          { col: 1, row: 1 },
  product_list:    { col: 2, row: 1 },
  product_detail:  { col: 3, row: 1 },
  evaluate_item:   { col: 4, row: 1 },
  // Row 2 — Conversion (7 stations)
  add_to_cart:          { col: 0, row: 2 },
  continue_or_checkout: { col: 1, row: 2 },
  checkout_decision:    { col: 2, row: 2 },
  pay:                  { col: 3, row: 2 },
  write_review:         { col: 4, row: 2 },
  abandon:              { col: 5, row: 2 },
  purchased:            { col: 6, row: 2 },
  // Row 3 — Seller flow (10 stations) — agentes vendedores
  seller_idle:                { col: 0, row: 3 },
  seller_login:               { col: 1, row: 3 },
  seller_audit:               { col: 2, row: 3 },
  seller_check_notifications: { col: 3, row: 3 },
  seller_decide:              { col: 4, row: 3 },
  seller_restock:             { col: 5, row: 3 },
  seller_suspend:             { col: 6, row: 3 },
  seller_create_product:      { col: 7, row: 3 },
  seller_update_price:        { col: 8, row: 3 },
  seller_done:                { col: 9, row: 3 },
};

const ROW_LABELS = [
  'ENTRY / DECISION',
  'NAVIGATION / DISCOVERY',
  'CONVERSION',
  'SELLERS — INVENTORY MGMT',
];
const ROW_COLS = [4, 5, 7, 10];

/** current_page legado vs id do quadrante (STATIONS / graph node). Sem isso, bolinhas somem da grade. */
function canonicalStationId(station) {
  if (!station) return station;
  const aliases = {
    home: 'browse_home',
    cart: 'add_to_cart',
    checkout: 'checkout_decision',
    paid: 'pay',
    end: 'abandon',
    review_written: 'write_review',
    start: 'waiting_pool',
    continue: 'continue_or_checkout',
  };
  return aliases[station] || station;
}

/* ── Agent Dot ── */
const AgentDot = React.memo(function AgentDot({ agent, onClick, dimmed, showLabels }) {
  const dotSize = 12;
  const isIdle = agent.status === 'idle';
  const isQwen = !isIdle && agent.isThinking && ['decide_session','evaluate_item','checkout_decision'].includes(agent.station);

  // Cor: idle = neutro (cinza); erro = vermelho; purchased = verde; senão cor do archetype.
  const bg = isIdle
    ? 'rgba(100,116,139,0.55)'         // slate-500 translucido
    : agent.hasError
      ? '#EF4444'
      : agent.outcome === 'purchased'
        ? '#22C55E'
        : agent.persona.color;

  const storeLabel = agent.persona.storeName ? ` @ ${agent.persona.storeName}` : '';
  const tooltipName = isIdle
    ? `${agent.workerId} — idle`
    : `${agent.workerId || agent.id} • ${agent.persona.name}${storeLabel} (${agent.sessionId})`;

  return (
    <div
      onClick={() => onClick(agent)}
      title={tooltipName}
      style={{
        width: dotSize,
        height: dotSize,
        borderRadius: '50%',
        background: bg,
        border: isIdle ? '1px dashed rgba(148,163,184,0.5)' : 'none',
        opacity: dimmed ? 0.12 : (isIdle ? 0.55 : 1),
        cursor: 'pointer',
        position: 'relative',
        transition: 'opacity 0.3s, transform 0.3s ease-out, box-shadow 0.3s, background 0.3s',
        boxShadow: isQwen
          ? `0 0 8px 3px rgba(168,85,247,0.6)`
          : agent.outcome === 'purchased'
            ? `0 0 6px 2px rgba(34,197,94,0.5)`
            : 'none',
        animation: isQwen ? 'qwenPulse 1.5s ease-in-out infinite' :
                   agent.hasError ? 'errorBlink 0.5s ease-in-out 3' : 'none',
        flexShrink: 0,
        zIndex: 2,
      }}
    >
      {agent.rateLimited && (
        <span style={{position:'absolute',top:-10,left:2,fontSize:8,lineHeight:1}}>⚠️</span>
      )}
    </div>
  );
});

/* ── Station Box ── */
const StationBox = React.memo(function StationBox({ station, agents, onAgentClick, dimmedAgents, showLabels, totalAgentCount }) {
  const count = agents.length;
  const maxIntensity = Math.min(count / Math.max(totalAgentCount * 0.15, 1), 1);
  const isQwen = station.isQwen;
  const thinkingAgents = agents.filter(a => a.isThinking);
  const avgProgress = thinkingAgents.length > 0
    ? thinkingAgents.reduce((s, a) => s + a.thinkingProgress, 0) / thinkingAgents.length
    : 0;

  const glowColor = isQwen ? `rgba(168,85,247,${0.1 + maxIntensity * 0.4})` : `rgba(51,131,250,${0.05 + maxIntensity * 0.25})`;
  const borderColor = isQwen ? `rgba(168,85,247,${0.3 + maxIntensity * 0.4})` : `rgba(71,85,105,${0.2 + maxIntensity * 0.3})`;

  return (
    <div style={{
      background: `rgba(30,41,59,${0.5 + maxIntensity * 0.3})`,
      border: `1px solid ${borderColor}`,
      borderRadius: 14,
      padding: '10px 12px 8px',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      minHeight: 90,
      position: 'relative',
      backdropFilter: 'blur(8px)',
      boxShadow: count > 0 ? `0 0 ${12 + maxIntensity * 20}px ${glowColor}, inset 0 1px 0 rgba(255,255,255,0.05)` : 'inset 0 1px 0 rgba(255,255,255,0.03)',
      transition: 'box-shadow 0.5s, border-color 0.5s',
      flex: 1,
      minWidth: 0,
    }}
      aria-label={`Station: ${station.label}, ${count} agents`}
    >
      {/* Header */}
      <div style={{display:'flex',alignItems:'center',gap:5,marginBottom:2}}>
        <Icon name={station.icon} size={14} className="" />
        {showLabels && <span style={{fontSize:10,color: isQwen ? '#C4B5FD' : '#94A3B8',fontWeight:600,letterSpacing:'0.3px',textTransform:'uppercase',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{station.label}</span>}
        {isQwen && <span style={{fontSize:9,marginLeft:'auto'}}>🧠</span>}
        <span style={{fontSize:11,fontWeight:700,color: count > 0 ? '#E2E8F0' : '#475569',marginLeft: showLabels ? 0 : 'auto',fontVariantNumeric:'tabular-nums'}}>{count}</span>
      </div>

      {/* Qwen progress bar */}
      {isQwen && thinkingAgents.length > 0 && (
        <div style={{width:'100%',height:3,background:'rgba(168,85,247,0.15)',borderRadius:2,overflow:'hidden'}}>
          <div style={{width:`${avgProgress*100}%`,height:'100%',background:'linear-gradient(90deg,#A855F7,#7C3AED)',borderRadius:2,transition:'width 0.15s linear'}}></div>
        </div>
      )}

      {/* Agent dots grid */}
      <div style={{display:'flex',flexWrap:'wrap',gap:3,alignContent:'flex-start',flex:1,minHeight:20}}>
        {agents.map(agent => (
          <AgentDot
            key={agent.workerId || agent.id}
            agent={agent}
            onClick={onAgentClick}
            dimmed={dimmedAgents.has(agent.workerId || agent.id)}
            showLabels={showLabels}
          />
        ))}
      </div>
    </div>
  );
});

/* ── Floor Plan ── */
const FloorPlan = React.memo(function FloorPlan({ agents, stations, onAgentClick, filters, showLabels }) {
  // Group agents by station
  const agentsByStation = React.useMemo(() => {
    const map = {};
    stations.forEach(s => { map[s.id] = []; });
    agents.forEach(a => {
      const sid = canonicalStationId(a.station);
      if (map[sid]) map[sid].push(a);
    });
    return map;
  }, [agents, stations]);

  // Compute dimmed set based on filters
  const dimmedAgents = React.useMemo(() => {
    const set = new Set();
    const hasFilters = filters.agentKinds?.length > 0
      || filters.archetypes.length > 0
      || filters.sellerArchetypes?.length > 0
      || filters.intents.length > 0
      || filters.errorsOnly
      || filters.searchId;
    if (!hasFilters) return set;
    agents.forEach(a => {
      let matches = true;
      const kind = a.kind || 'buyer';
      if (filters.agentKinds?.length > 0 && !filters.agentKinds.includes(kind)) matches = false;
      if (kind === 'seller') {
        if (filters.sellerArchetypes?.length > 0 && !filters.sellerArchetypes.includes(a.persona.archetype)) matches = false;
      } else if (filters.archetypes.length > 0 && !filters.archetypes.includes(a.persona.archetype)) {
        matches = false;
      }
      if (filters.intents.length > 0 && !filters.intents.includes(a.intent)) matches = false;
      if (filters.errorsOnly && !a.hasError) matches = false;
      if (filters.searchId
          && !a.sessionId.includes(filters.searchId)
          && !(a.workerId || '').includes(filters.searchId)) matches = false;
      if (!matches) set.add(a.workerId || a.id);
    });
    return set;
  }, [agents, filters]);

  // Build rows (0-3 — sellers vão na row 3)
  const rows = [0, 1, 2, 3].map(rowIdx => {
    return stations.filter(s => STATION_LAYOUT[s.id]?.row === rowIdx)
      .sort((a, b) => STATION_LAYOUT[a.id].col - STATION_LAYOUT[b.id].col);
  });

  return (
    <div style={floorStyles.container}>
      {rows.map((rowStations, rowIdx) => (
        <div key={rowIdx} style={floorStyles.rowWrapper}>
          <div style={floorStyles.rowLabel}>{ROW_LABELS[rowIdx]}</div>
          <div style={floorStyles.row}>
            {rowStations.map(station => (
              <StationBox
                key={station.id}
                station={station}
                agents={agentsByStation[station.id] || []}
                onAgentClick={onAgentClick}
                dimmedAgents={dimmedAgents}
                showLabels={showLabels}
                totalAgentCount={agents.length}
              />
            ))}
          </div>
        </div>
      ))}

      {/* Connection arrows (decorative) */}
      <svg style={floorStyles.arrowsSvg} viewBox="0 0 1200 50" preserveAspectRatio="none">
        <defs>
          <marker id="arrowhead" markerWidth="6" markerHeight="4" refX="6" refY="2" orient="auto">
            <polygon points="0 0, 6 2, 0 4" fill="rgba(100,116,139,0.3)" />
          </marker>
        </defs>
      </svg>
    </div>
  );
});

const floorStyles = {
  container: { display:'flex', flexDirection:'column', gap:16, padding:'12px 16px', flex:1, overflowY:'auto', position:'relative' },
  rowWrapper: { display:'flex', flexDirection:'column', gap:6 },
  rowLabel: { fontSize:10, color:'#475569', fontWeight:700, letterSpacing:'1.5px', textTransform:'uppercase', paddingLeft:4 },
  row: { display:'flex', gap:8 },
  arrowsSvg: { position:'absolute', left:0, right:0, bottom:0, height:30, pointerEvents:'none' },
};

/* ── Mini Map ── */
const MiniMap = React.memo(function MiniMap({ agents, stations }) {
  const canvasRef = React.useRef(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    // Draw station rects
    ctx.fillStyle = 'rgba(30,41,59,0.6)';
    stations.forEach(s => {
      const layout = STATION_LAYOUT[s.id];
      if (!layout) return;
      const cols = ROW_COLS[layout.row];
      const x = (layout.col / cols) * w + 2;
      const y = (layout.row / 3) * h + 4;
      const sw = (w / cols) - 4;
      const sh = (h / 3) - 8;
      ctx.fillRect(x, y, sw, sh);
    });

    // Draw agent dots
    agents.forEach(a => {
      const layout = STATION_LAYOUT[a.station];
      if (!layout) return;
      const cols = ROW_COLS[layout.row];
      const x = (layout.col / cols) * w + Math.random() * ((w / cols) - 6) + 3;
      const y = (layout.row / 3) * h + Math.random() * ((h / 3) - 10) + 6;
      ctx.fillStyle = a.persona.color;
      ctx.globalAlpha = 0.8;
      ctx.beginPath();
      ctx.arc(x, y, 1.5, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
  }, [agents, stations]);

  return (
    <div style={miniMapStyles.container}>
      <span style={miniMapStyles.label}>Mini Map</span>
      <canvas ref={canvasRef} width={200} height={90} style={miniMapStyles.canvas}></canvas>
    </div>
  );
});

const miniMapStyles = {
  container: { position:'fixed', bottom:180, left:200, background:'rgba(15,23,42,0.9)', border:'1px solid rgba(71,85,105,0.3)', borderRadius:10, padding:'6px 8px', backdropFilter:'blur(8px)', zIndex:50 },
  label: { fontSize:9, color:'#64748B', textTransform:'uppercase', letterSpacing:'0.5px', fontWeight:600 },
  canvas: { display:'block', borderRadius:6, marginTop:4 },
};

/* ── Health Gauge ── */
const HealthGauge = React.memo(function HealthGauge({ kpis }) {
  // Health 0-100 based on error rate, Qwen latency, queue ratio
  const errorPenalty = Math.min(kpis.errorsLast5Min * 5, 40);
  const latencyPenalty = Math.min(parseFloat(kpis.p95QwenLatency) * 5, 30);
  const health = Math.max(0, Math.min(100, 100 - errorPenalty - latencyPenalty));
  const color = health > 70 ? '#22C55E' : health > 40 ? '#F97316' : '#EF4444';
  const angle = (health / 100) * 180;

  return (
    <div style={gaugeStyles.container}>
      <span style={gaugeStyles.label}>System Health</span>
      <svg width="70" height="40" viewBox="0 0 70 40">
        <path d="M 5 38 A 30 30 0 0 1 65 38" fill="none" stroke="rgba(71,85,105,0.3)" strokeWidth="5" strokeLinecap="round" />
        <path d="M 5 38 A 30 30 0 0 1 65 38" fill="none" stroke={color} strokeWidth="5" strokeLinecap="round"
          strokeDasharray={`${(angle / 180) * 94} 94`} style={{transition:'stroke-dasharray 0.5s'}} />
        <text x="35" y="36" textAnchor="middle" fill={color} fontSize="14" fontWeight="700">{Math.round(health)}</text>
      </svg>
    </div>
  );
});

const gaugeStyles = {
  container: { position:'fixed', bottom:180, right:16, background:'rgba(15,23,42,0.9)', border:'1px solid rgba(71,85,105,0.3)', borderRadius:10, padding:'6px 10px', backdropFilter:'blur(8px)', zIndex:50, display:'flex', flexDirection:'column', alignItems:'center', gap:2 },
  label: { fontSize:9, color:'#64748B', textTransform:'uppercase', letterSpacing:'0.5px', fontWeight:600 },
};

Object.assign(window, { FloorPlan, MiniMap, HealthGauge, STATION_LAYOUT, ROW_LABELS, ROW_COLS });
