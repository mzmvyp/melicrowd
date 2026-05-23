/**
 * MeliCrowd Live Floor — UI Components (Part 1)
 * Header, KPI Cards, Sidebar Filters
 */

/* ── Lucide icon helper (inline SVGs) ── */
const LucideIcons = {
  Clock: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
  UserRound: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="5"/><path d="M20 21a8 8 0 0 0-16 0"/></svg>,
  Brain: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5a3 3 0 1 0-5.997.125 4 4 0 0 0-2.526 5.77 4 4 0 0 0 .556 6.588A4 4 0 1 0 12 18Z"/><path d="M12 5a3 3 0 1 1 5.997.125 4 4 0 0 1 2.526 5.77 4 4 0 0 1-.556 6.588A4 4 0 1 1 12 18Z"/><path d="M15 13a4.5 4.5 0 0 1-3-4 4.5 4.5 0 0 1-3 4"/><path d="M17.599 6.5a3 3 0 0 0 .399-1.375"/><path d="M6.003 5.125A3 3 0 0 0 6.401 6.5"/><path d="M3.477 10.896a4 4 0 0 1 .585-.396"/><path d="M19.938 10.5a4 4 0 0 1 .585.396"/><path d="M6 18a4 4 0 0 1-1.967-.516"/><path d="M19.967 17.484A4 4 0 0 1 18 18"/></svg>,
  KeyRound: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 18v3c0 .6.4 1 1 1h4v-3h3v-3h2l1.4-1.4a6.5 6.5 0 1 0-4-4Z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/></svg>,
  Home: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>,
  Search: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>,
  List: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="8" x2="21" y1="6" y2="6"/><line x1="8" x2="21" y1="12" y2="12"/><line x1="8" x2="21" y1="18" y2="18"/><line x1="3" x2="3.01" y1="6" y2="6"/><line x1="3" x2="3.01" y1="12" y2="12"/><line x1="3" x2="3.01" y1="18" y2="18"/></svg>,
  Package: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/></svg>,
  ShoppingCart: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/></svg>,
  GitFork: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M18 9v2c0 .6-.4 1-1 1H7c-.6 0-1-.4-1-1V9"/><path d="M12 12v3"/></svg>,
  CreditCard: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/></svg>,
  Star: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>,
  XCircle: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/></svg>,
  CheckCircle: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>,
  Activity: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/></svg>,
  AlertTriangle: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>,
  Play: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="6 3 20 12 6 21 6 3"/></svg>,
  Pause: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="4" height="16" x="6" y="4"/><rect width="4" height="16" x="14" y="4"/></svg>,
  Square: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="18" x="3" y="3" rx="2"/></svg>,
  Filter: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>,
  X: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>,
  Eye: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>,
  Users: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
  Zap: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/></svg>,
  TrendingUp: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>,
  Timer: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="10" x2="14" y1="2" y2="2"/><line x1="12" x2="15" y1="14" y2="11"/><circle cx="12" cy="14" r="8"/></svg>,
  Crosshair: (props) => <svg xmlns="http://www.w3.org/2000/svg" width={props.size||18} height={props.size||18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="22" x2="18" y1="12" y2="12"/><line x1="6" x2="2" y1="12" y2="12"/><line x1="12" x2="12" y1="6" y2="2"/><line x1="12" x2="12" y1="22" y2="18"/></svg>,
};

function Icon({ name, size = 18, className = '' }) {
  const IconComp = LucideIcons[name];
  if (!IconComp) return null;
  return <span className={className} style={{ display: 'inline-flex', alignItems: 'center' }}><IconComp size={size} /></span>;
}

/* ── Header Component ── */
const Header = React.memo(function Header({ kpis, controls, connectionStatus, onSeedPersonas }) {
  const { isRunning, setIsRunning, agentCount, setAgentCount, showTrails, setShowTrails, showLabels, setShowLabels, scalePool } = controls;
  const wsBadgeColor = connectionStatus === 'open' ? '#22C55E' : connectionStatus === 'connecting' ? '#FACC15' : '#EF4444';
  const wsBadgeLabel = connectionStatus === 'open' ? 'LIVE' : connectionStatus === 'connecting' ? 'CONNECTING' : 'OFFLINE';

  const total = kpis.totalWorkers ?? 0;
  const busy = kpis.busyWorkers ?? kpis.activeAgents ?? 0;
  const idle = kpis.idleWorkers ?? Math.max(total - busy, 0);
  const util = kpis.utilization ?? '0.0';
  const utilNum = parseFloat(util);
  const utilColor = utilNum >= 90 ? '#EF4444' : utilNum >= 70 ? '#F97316' : '#22C55E';

  const kpiCards = [
    { label: 'Workers', value: total, icon: 'Users', color: '#E2E8F0' },
    { label: 'Busy', value: busy, icon: 'Activity', color: '#3483FA' },
    { label: 'Idle', value: idle, icon: 'Clock', color: '#94A3B8' },
    { label: 'Utilization', value: `${util}%`, icon: 'TrendingUp', color: utilColor },
    { label: 'Sessions/min', value: kpis.sessionsPerMin, icon: 'Activity', color: '#22C55E' },
    { label: 'Conversion', value: `${kpis.conversionRate}%`, icon: 'TrendingUp', color: '#22C55E' },
    { label: 'Cart Abandon', value: `${kpis.cartAbandonmentRate}%`, icon: 'ShoppingCart', color: '#F97316' },
    { label: 'Qwen/min', value: kpis.qwenCallsPerMin, icon: 'Brain', color: '#A855F7' },
    { label: 'P95 Latency', value: `${kpis.p95QwenLatency}s`, icon: 'Zap', color: '#FACC15' },
    { label: 'Errors (5m)', value: kpis.errorsLast5Min, icon: 'AlertTriangle', color: kpis.errorsLast5Min > 5 ? '#EF4444' : '#64748B' },
  ];

  return (
    <header style={headerStyles.container}>
      <div style={headerStyles.left}>
        <div style={headerStyles.logo}>
          <span style={headerStyles.logoIcon}>⚡</span>
          <span style={headerStyles.logoText}>MeliCrowd</span>
          <span style={headerStyles.logoSub}>Live Floor</span>
        </div>
        <div style={{...headerStyles.statusDot, background: isRunning ? '#22C55E' : '#EF4444'}}></div>
        <span style={headerStyles.statusLabel}>{isRunning ? 'Running' : 'Stopped'}</span>
      </div>

      <div style={headerStyles.kpiRow}>
        {kpiCards.map(k => (
          <div key={k.label} style={headerStyles.kpiCard}>
            <div style={{display:'flex',alignItems:'center',gap:4}}>
              <Icon name={k.icon} size={13} className="" />
              <span style={headerStyles.kpiLabel}>{k.label}</span>
            </div>
            <span style={{...headerStyles.kpiValue, color: k.color}}>{k.value}</span>
          </div>
        ))}
      </div>

      <div style={headerStyles.controls}>
        <span title={`WebSocket: ${connectionStatus}`} style={{
          ...headerStyles.wsBadge,
          background: `${wsBadgeColor}22`,
          border: `1px solid ${wsBadgeColor}66`,
          color: wsBadgeColor,
        }}>
          <span style={{...headerStyles.wsDot, background: wsBadgeColor}}></span>
          {wsBadgeLabel}
        </span>
        <label style={headerStyles.sliderLabel}>
          Agents: {agentCount}
          <input type="range" min={1} max={500} value={agentCount}
            onChange={e => setAgentCount(Number(e.target.value))}
            onMouseUp={() => isRunning && scalePool && scalePool(agentCount)}
            style={headerStyles.slider} />
        </label>
        <div style={headerStyles.btnGroup}>
          <button onClick={() => setIsRunning(!isRunning)} style={headerStyles.btn}
            aria-label={isRunning ? 'Stop pool' : 'Start pool'}>
            <Icon name={isRunning ? 'Square' : 'Play'} size={14} />
          </button>
        </div>
        {onSeedPersonas && (
          <button onClick={() => {
            const n = Number(prompt('Quantas personas gerar via Qwen?', '50'));
            if (n > 0) onSeedPersonas(n);
          }} style={headerStyles.toggleBtn} title="Generate personas via Qwen">
            Seed personas
          </button>
        )}
        <button onClick={() => setShowTrails(!showTrails)} style={{...headerStyles.toggleBtn, opacity: showTrails ? 1 : 0.4}} title="Toggle trails">
          Trails
        </button>
        <button onClick={() => setShowLabels(!showLabels)} style={{...headerStyles.toggleBtn, opacity: showLabels ? 1 : 0.4}} title="Toggle labels">
          Labels
        </button>
      </div>
    </header>
  );
});

const headerStyles = {
  container: { display:'flex', alignItems:'center', justifyContent:'space-between', padding:'8px 16px', background:'rgba(15,23,42,0.95)', borderBottom:'1px solid rgba(71,85,105,0.3)', backdropFilter:'blur(12px)', position:'fixed', top:0, left:0, right:0, zIndex:100, gap:12, flexWrap:'wrap', minHeight:56 },
  left: { display:'flex', alignItems:'center', gap:10, flexShrink:0 },
  logo: { display:'flex', alignItems:'center', gap:6 },
  logoIcon: { fontSize:22 },
  logoText: { fontSize:18, fontWeight:700, color:'#FFE600', letterSpacing:'-0.5px' },
  logoSub: { fontSize:13, color:'#94A3B8', fontWeight:400, marginLeft:2 },
  statusDot: { width:8, height:8, borderRadius:'50%', flexShrink:0 },
  statusLabel: { fontSize:12, color:'#94A3B8' },
  kpiRow: { display:'flex', gap:6, flexWrap:'wrap', flex:1, justifyContent:'center' },
  kpiCard: { display:'flex', flexDirection:'column', gap:1, padding:'4px 10px', background:'rgba(30,41,59,0.7)', borderRadius:8, border:'1px solid rgba(71,85,105,0.2)', minWidth:90 },
  kpiLabel: { fontSize:10, color:'#94A3B8', textTransform:'uppercase', letterSpacing:'0.5px' },
  kpiValue: { fontSize:16, fontWeight:700, fontVariantNumeric:'tabular-nums' },
  controls: { display:'flex', alignItems:'center', gap:8, flexShrink:0 },
  sliderLabel: { fontSize:11, color:'#CBD5E1', display:'flex', flexDirection:'column', gap:2, minWidth:100 },
  slider: { width:'100%', accentColor:'#FFE600', height:4, cursor:'pointer' },
  btnGroup: { display:'flex', gap:4 },
  btn: { background:'rgba(51,131,250,0.2)', border:'1px solid rgba(51,131,250,0.4)', borderRadius:6, padding:'6px 8px', color:'#3483FA', cursor:'pointer', display:'flex', alignItems:'center' },
  select: { background:'rgba(30,41,59,0.9)', border:'1px solid rgba(71,85,105,0.3)', borderRadius:6, padding:'4px 8px', color:'#E2E8F0', fontSize:12, cursor:'pointer' },
  toggleBtn: { background:'rgba(30,41,59,0.9)', border:'1px solid rgba(71,85,105,0.3)', borderRadius:6, padding:'4px 10px', color:'#E2E8F0', fontSize:11, cursor:'pointer', transition:'opacity 0.2s' },
  wsBadge: { display:'inline-flex', alignItems:'center', gap:4, padding:'3px 8px', borderRadius:5, fontSize:10, fontWeight:700, letterSpacing:'0.5px', fontFamily:"'JetBrains Mono', monospace" },
  wsDot: { width:6, height:6, borderRadius:'50%' },
};

/* ── Sidebar Filters ── */
const Sidebar = React.memo(function Sidebar({ filters, setFilters, archetypes }) {
  const toggleArchetype = (key) => {
    setFilters(prev => ({
      ...prev,
      archetypes: prev.archetypes.includes(key)
        ? prev.archetypes.filter(k => k !== key)
        : [...prev.archetypes, key],
    }));
  };
  const toggleIntent = (key) => {
    setFilters(prev => ({
      ...prev,
      intents: prev.intents.includes(key)
        ? prev.intents.filter(k => k !== key)
        : [...prev.intents, key],
    }));
  };

  return (
    <aside style={sidebarStyles.container}>
      <div style={sidebarStyles.header}>
        <Icon name="Filter" size={14} />
        <span style={sidebarStyles.title}>Filters</span>
      </div>
      <div style={{fontSize:10, color:'#475569', padding:'2px 0 6px', borderBottom:'1px solid rgba(71,85,105,0.15)'}}>
        Filtros aplicam ao snapshot atual.
      </div>

      <div style={sidebarStyles.section}>
        <span style={sidebarStyles.sectionTitle}>Persona Archetype</span>
        {archetypes.map(a => (
          <label key={a.key} style={sidebarStyles.checkLabel}>
            <input type="checkbox" checked={filters.archetypes.includes(a.key)}
              onChange={() => toggleArchetype(a.key)} style={{accentColor: a.color}} />
            <span style={{...sidebarStyles.dot, background: a.color}}></span>
            <span style={sidebarStyles.checkText}>{a.label}</span>
          </label>
        ))}
      </div>

      <div style={sidebarStyles.section}>
        <span style={sidebarStyles.sectionTitle}>Session Intent</span>
        {INTENTS.map(i => (
          <label key={i} style={sidebarStyles.checkLabel}>
            <input type="checkbox" checked={filters.intents.includes(i)}
              onChange={() => toggleIntent(i)} style={{accentColor:'#3483FA'}} />
            <span style={sidebarStyles.checkText}>{i}</span>
          </label>
        ))}
      </div>

      <div style={sidebarStyles.section}>
        <label style={sidebarStyles.checkLabel}>
          <input type="checkbox" checked={filters.errorsOnly}
            onChange={() => setFilters(prev => ({...prev, errorsOnly: !prev.errorsOnly}))} 
            style={{accentColor:'#EF4444'}} />
          <span style={sidebarStyles.checkText}>Errors only</span>
        </label>
      </div>

      <div style={sidebarStyles.section}>
        <span style={sidebarStyles.sectionTitle}>Search Session</span>
        <input type="text" placeholder="session_id..." value={filters.searchId}
          onChange={e => setFilters(prev => ({...prev, searchId: e.target.value}))}
          style={sidebarStyles.input} />
      </div>
    </aside>
  );
});

const sidebarStyles = {
  container: { width:190, background:'rgba(15,23,42,0.92)', borderRight:'1px solid rgba(71,85,105,0.2)', padding:'12px 10px', display:'flex', flexDirection:'column', gap:14, overflowY:'auto', backdropFilter:'blur(8px)', flexShrink:0 },
  header: { display:'flex', alignItems:'center', gap:6, color:'#E2E8F0' },
  title: { fontSize:13, fontWeight:600, color:'#E2E8F0' },
  section: { display:'flex', flexDirection:'column', gap:5 },
  sectionTitle: { fontSize:10, color:'#64748B', textTransform:'uppercase', letterSpacing:'0.5px', fontWeight:600, marginBottom:2 },
  checkLabel: { display:'flex', alignItems:'center', gap:6, cursor:'pointer', fontSize:12, color:'#CBD5E1' },
  checkText: { fontSize:12, textTransform:'capitalize' },
  dot: { width:8, height:8, borderRadius:'50%', flexShrink:0 },
  input: { background:'rgba(30,41,59,0.9)', border:'1px solid rgba(71,85,105,0.3)', borderRadius:6, padding:'5px 8px', color:'#E2E8F0', fontSize:12, outline:'none', width:'100%' },
};

Object.assign(window, { Icon, LucideIcons, Header, Sidebar });
