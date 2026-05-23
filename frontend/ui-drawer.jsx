/**
 * MeliCrowd Live Floor — Agent Drawer + Event Stream
 */

/* ── Agent Detail Drawer ── */
const AgentDrawer = React.memo(function AgentDrawer({ agent, onClose, onFollow }) {
  if (!agent) return null;
  const p = agent.persona;
  const initials = p.name.split(' ').map(n => n[0]).join('').slice(0, 2);
  const sessionDuration = ((Date.now() - agent.startedAt) / 1000).toFixed(0);

  // Sparkline of Qwen latencies
  const latencies = agent.qwenLatencies || [];
  const maxLat = Math.max(...latencies, 1);
  const sparkW = 160;
  const sparkH = 32;
  const sparkPoints = latencies.map((l, i) => {
    const x = latencies.length > 1 ? (i / (latencies.length - 1)) * sparkW : sparkW / 2;
    const y = sparkH - (l / maxLat) * (sparkH - 4) - 2;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div style={drawerStyles.overlay} onClick={onClose}>
      <div style={drawerStyles.container} onClick={e => e.stopPropagation()}>
        {/* Close button */}
        <button onClick={onClose} style={drawerStyles.closeBtn} aria-label="Close drawer">
          <Icon name="X" size={16} />
        </button>

        {/* Persona header */}
        <div style={drawerStyles.personaHeader}>
          <div style={{...drawerStyles.avatar, background: p.color}}>
            <span style={drawerStyles.avatarText}>{initials}</span>
          </div>
          <div style={drawerStyles.personaInfo}>
            <span style={drawerStyles.personaName}>{p.name}</span>
            <span style={drawerStyles.personaMeta}>{p.age} anos · {p.city}, {p.state}</span>
            <span style={drawerStyles.personaMeta}>Class {p.incomeClass} · {p.archetype.replace('_', ' ')}</span>
          </div>
        </div>

        {/* Quick stats */}
        <div style={drawerStyles.statsRow}>
          <div style={drawerStyles.stat}>
            <span style={drawerStyles.statLabel}>Session</span>
            <span style={drawerStyles.statValue}>{agent.sessionId}</span>
          </div>
          <div style={drawerStyles.stat}>
            <span style={drawerStyles.statLabel}>Duration</span>
            <span style={drawerStyles.statValue}>{sessionDuration}s</span>
          </div>
          <div style={drawerStyles.stat}>
            <span style={drawerStyles.statLabel}>Cart</span>
            <span style={drawerStyles.statValue}>R$ {agent.cartTotal.toFixed(2)}</span>
          </div>
          <div style={drawerStyles.stat}>
            <span style={drawerStyles.statLabel}>Qwen Calls</span>
            <span style={drawerStyles.statValue}>{agent.qwenCalls}</span>
          </div>
        </div>

        {/* Intent & Status */}
        <div style={drawerStyles.section}>
          <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
            <span style={{...drawerStyles.badge, background:'rgba(51,131,250,0.2)', color:'#3483FA'}}>Intent: {agent.intent}</span>
            <span style={{...drawerStyles.badge, background: agent.outcome === 'purchased' ? 'rgba(34,197,94,0.2)' : agent.outcome ? 'rgba(249,115,22,0.2)' : 'rgba(100,116,139,0.2)',
              color: agent.outcome === 'purchased' ? '#22C55E' : agent.outcome ? '#F97316' : '#94A3B8'}}>
              {agent.outcome || agent.station}
            </span>
          </div>
        </div>

        {/* Follow button */}
        <button onClick={() => onFollow(agent.id)} style={drawerStyles.followBtn}>
          <Icon name="Crosshair" size={14} />
          <span>Follow this agent</span>
        </button>

        {/* Decision Trace Timeline */}
        <div style={drawerStyles.section}>
          <span style={drawerStyles.sectionTitle}>Decision Trace</span>
          <div style={drawerStyles.timeline}>
            {agent.decisionTrace.length === 0 && (
              <span style={{fontSize:11,color:'#475569',fontStyle:'italic'}}>No Qwen calls yet</span>
            )}
            {agent.decisionTrace.map((d, i) => (
              <div key={i} style={drawerStyles.timelineItem}>
                <div style={drawerStyles.timelineDot}></div>
                <div style={drawerStyles.timelineContent}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                    <span style={drawerStyles.timelineNode}>🧠 {d.node}</span>
                    <span style={drawerStyles.timelineLatency}>{d.latencyMs}ms</span>
                  </div>
                  <span style={drawerStyles.timelineDetail}>
                    Decision: {d.decision} · {d.promptChars} chars
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Cart */}
        {agent.cartItems.length > 0 && (
          <div style={drawerStyles.section}>
            <span style={drawerStyles.sectionTitle}>Cart ({agent.cartItems.length} items)</span>
            {agent.cartItems.map((item, i) => (
              <div key={i} style={drawerStyles.cartItem}>
                <span style={drawerStyles.cartItemTitle}>{item.title}</span>
                <span style={drawerStyles.cartItemPrice}>R$ {item.price.toFixed(2)}</span>
              </div>
            ))}
            <div style={{...drawerStyles.cartItem, borderTop:'1px solid rgba(71,85,105,0.3)', paddingTop:6, marginTop:4}}>
              <span style={{...drawerStyles.cartItemTitle, fontWeight:700}}>Total</span>
              <span style={{...drawerStyles.cartItemPrice, fontWeight:700, color:'#FFE600'}}>R$ {agent.cartTotal.toFixed(2)}</span>
            </div>
          </div>
        )}

        {/* Qwen Latency Sparkline */}
        {latencies.length > 1 && (
          <div style={drawerStyles.section}>
            <span style={drawerStyles.sectionTitle}>Qwen Latencies</span>
            <svg width={sparkW} height={sparkH} style={{display:'block'}}>
              <polyline points={sparkPoints} fill="none" stroke="#A855F7" strokeWidth="1.5" />
              {latencies.map((l, i) => {
                const x = latencies.length > 1 ? (i / (latencies.length - 1)) * sparkW : sparkW / 2;
                const y = sparkH - (l / maxLat) * (sparkH - 4) - 2;
                return <circle key={i} cx={x} cy={y} r={2.5} fill="#A855F7" />;
              })}
            </svg>
          </div>
        )}
      </div>
    </div>
  );
});

const drawerStyles = {
  overlay: { position:'fixed', top:0, right:0, bottom:0, width:'100%', zIndex:200, display:'flex', justifyContent:'flex-end' },
  container: { width:340, background:'rgba(15,23,42,0.97)', borderLeft:'1px solid rgba(71,85,105,0.3)', padding:'16px', overflowY:'auto', backdropFilter:'blur(16px)', display:'flex', flexDirection:'column', gap:14, position:'relative' },
  closeBtn: { position:'absolute', top:12, right:12, background:'none', border:'none', color:'#94A3B8', cursor:'pointer', padding:4 },
  personaHeader: { display:'flex', gap:12, alignItems:'center' },
  avatar: { width:48, height:48, borderRadius:12, display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 },
  avatarText: { fontSize:18, fontWeight:700, color:'rgba(0,0,0,0.7)' },
  personaInfo: { display:'flex', flexDirection:'column', gap:2 },
  personaName: { fontSize:16, fontWeight:700, color:'#F1F5F9' },
  personaMeta: { fontSize:11, color:'#94A3B8' },
  statsRow: { display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 },
  stat: { display:'flex', flexDirection:'column', gap:1, padding:'6px 8px', background:'rgba(30,41,59,0.6)', borderRadius:8, border:'1px solid rgba(71,85,105,0.15)' },
  statLabel: { fontSize:9, color:'#64748B', textTransform:'uppercase', letterSpacing:'0.5px', fontWeight:600 },
  statValue: { fontSize:13, color:'#E2E8F0', fontWeight:600, fontVariantNumeric:'tabular-nums' },
  section: { display:'flex', flexDirection:'column', gap:6 },
  sectionTitle: { fontSize:10, color:'#64748B', textTransform:'uppercase', letterSpacing:'0.5px', fontWeight:700 },
  badge: { fontSize:11, padding:'3px 8px', borderRadius:6, fontWeight:600, textTransform:'capitalize' },
  followBtn: { display:'flex', alignItems:'center', justifyContent:'center', gap:6, padding:'8px 12px', background:'rgba(51,131,250,0.15)', border:'1px solid rgba(51,131,250,0.3)', borderRadius:8, color:'#3483FA', fontSize:12, fontWeight:600, cursor:'pointer', transition:'background 0.2s' },
  timeline: { display:'flex', flexDirection:'column', gap:0, position:'relative' },
  timelineItem: { display:'flex', gap:10, padding:'6px 0', borderLeft:'2px solid rgba(168,85,247,0.3)', marginLeft:5, paddingLeft:12, position:'relative' },
  timelineDot: { position:'absolute', left:-5, top:10, width:8, height:8, borderRadius:'50%', background:'#A855F7', border:'2px solid #0F172A' },
  timelineContent: { display:'flex', flexDirection:'column', gap:2, flex:1 },
  timelineNode: { fontSize:12, fontWeight:600, color:'#C4B5FD' },
  timelineLatency: { fontSize:11, color:'#A855F7', fontWeight:700, fontVariantNumeric:'tabular-nums' },
  timelineDetail: { fontSize:10, color:'#64748B' },
  cartItem: { display:'flex', justifyContent:'space-between', alignItems:'center', gap:8 },
  cartItemTitle: { fontSize:11, color:'#CBD5E1', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', flex:1 },
  cartItemPrice: { fontSize:11, color:'#94A3B8', fontVariantNumeric:'tabular-nums', flexShrink:0 },
};

/* ── Event Stream (Footer) ── */
const EventStream = React.memo(function EventStream({ events }) {
  const scrollRef = React.useRef(null);

  const getEventColor = (type) => {
    switch (type) {
      case 'purchased': return '#22C55E';
      case 'abandon': return '#F97316';
      case 'error': return '#EF4444';
      case 'qwen': return '#A855F7';
      case 'search': return '#3483FA';
      case 'cart': return '#FFE600';
      default: return '#64748B';
    }
  };

  const getEventIcon = (type) => {
    switch (type) {
      case 'purchased': return '✅';
      case 'abandon': return '❌';
      case 'error': return '🔴';
      case 'qwen': return '🧠';
      case 'search': return '🔍';
      case 'cart': return '🛒';
      default: return '▸';
    }
  };

  const formatTime = (date) => {
    return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  return (
    <div style={streamStyles.container}>
      <div style={streamStyles.header}>
        <Icon name="Activity" size={12} />
        <span style={streamStyles.title}>Event Stream</span>
        <span style={streamStyles.count}>{events.length} events</span>
      </div>
      <div ref={scrollRef} style={streamStyles.scrollArea}>
        {events.map(ev => (
          <div key={ev.id} style={streamStyles.event}>
            <span style={{...streamStyles.time}}>[{formatTime(ev.timestamp)}]</span>
            <span style={streamStyles.icon}>{getEventIcon(ev.type)}</span>
            <span style={{...streamStyles.agentTag, color: getEventColor(ev.type)}}>agent#{ev.sessionId.slice(0,4)}</span>
            <span style={streamStyles.arrow}>→</span>
            <span style={{...streamStyles.detail, color: getEventColor(ev.type)}}>{ev.detail}</span>
          </div>
        ))}
        {events.length === 0 && (
          <span style={{fontSize:11,color:'#475569',fontStyle:'italic',padding:'4px 0'}}>Waiting for events...</span>
        )}
      </div>
    </div>
  );
});

const streamStyles = {
  container: { background:'rgba(15,23,42,0.95)', borderTop:'1px solid rgba(71,85,105,0.2)', padding:'6px 12px', backdropFilter:'blur(8px)', flexShrink:0 },
  header: { display:'flex', alignItems:'center', gap:6, marginBottom:4, color:'#94A3B8' },
  title: { fontSize:11, fontWeight:600, color:'#94A3B8' },
  count: { fontSize:10, color:'#475569', marginLeft:'auto' },
  scrollArea: { maxHeight:120, overflowY:'auto', display:'flex', flexDirection:'column', gap:1, fontFamily:"'JetBrains Mono', 'Fira Code', 'SF Mono', monospace", fontSize:11 },
  event: { display:'flex', gap:5, alignItems:'center', lineHeight:1.5, whiteSpace:'nowrap' },
  time: { color:'#475569', fontVariantNumeric:'tabular-nums', flexShrink:0 },
  icon: { fontSize:10, flexShrink:0 },
  agentTag: { fontWeight:600, flexShrink:0 },
  arrow: { color:'#475569', flexShrink:0 },
  detail: { overflow:'hidden', textOverflow:'ellipsis' },
};

Object.assign(window, { AgentDrawer, EventStream });
