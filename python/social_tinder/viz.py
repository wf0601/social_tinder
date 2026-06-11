"""HTML rendering for the keyword network using vis-network (via CDN).

Two entry points:
  - ``interactive_page()``  -> full UI with live filter controls; fetches /api/network
  - ``static_page(network)`` -> self-contained HTML with the network inlined
"""

from __future__ import annotations

import json

# Matches CLUSTER_COLORS in the TS NetworkGraph component.
CLUSTER_COLORS = [
    "#ff5a7e", "#4cc9f0", "#ffd166", "#06d6a0", "#b388ff",
    "#f78c6b", "#83e377", "#ff9ff3", "#54a0ff", "#feca57",
]

_HEAD = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>🔥 Social Tinder</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
  :root { --bg:#0b0d12; --panel:#12151d; --border:#232838; --accent:#ff5a7e; --fg:#e7e9ee; }
  * { box-sizing: border-box; }
  html,body { margin:0; height:100%; background:var(--bg); color:var(--fg);
    font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
  header { display:flex; align-items:baseline; gap:12px; justify-content:space-between;
    padding:12px 18px; border-bottom:1px solid var(--border); background:var(--panel); }
  header h1 { font-size:18px; margin:0; font-weight:700; }
  header .accent { color:var(--accent); }
  header .sub { font-size:12px; color:rgba(255,255,255,.4); }
  .badge { font-size:12px; padding:4px 10px; border-radius:999px; font-weight:600; }
  .badge.sample { background:rgba(245,158,11,.15); color:#fcd34d; }
  .badge.brandwatch { background:rgba(16,185,129,.15); color:#6ee7b7; }
  .layout { display:flex; height:calc(100% - 49px); }
  aside { width:280px; flex:none; overflow-y:auto; padding:16px; background:var(--panel);
    border-right:1px solid var(--border); }
  aside.right { border-right:none; border-left:1px solid var(--border); width:300px; }
  .field { margin-bottom:16px; }
  .field label { display:block; font-size:11px; text-transform:uppercase; letter-spacing:.05em;
    color:rgba(255,255,255,.4); font-weight:600; margin-bottom:6px; }
  .field .row { display:flex; justify-content:space-between; }
  .field .val { font-size:12px; color:rgba(255,255,255,.7); font-family:monospace; }
  input[type=range] { width:100%; accent-color:var(--accent); }
  input[type=text] { width:100%; background:var(--bg); border:1px solid var(--border);
    color:var(--fg); padding:8px 10px; border-radius:6px; font-size:13px; }
  #graph { flex:1; min-width:0; }
  .legend li { display:flex; align-items:center; gap:8px; font-size:12px; margin:6px 0;
    color:rgba(255,255,255,.7); }
  .dot { width:12px; height:12px; border-radius:50%; display:inline-block; }
  .stat { border:1px solid var(--border); background:var(--bg); border-radius:6px;
    padding:8px; text-align:center; }
  .stat .v { font-weight:600; font-size:14px; }
  .stat .k { font-size:10px; text-transform:uppercase; color:rgba(255,255,255,.4); }
  .conn { margin:8px 0; cursor:pointer; }
  .conn .bar { height:6px; background:rgba(255,255,255,.1); border-radius:999px; overflow:hidden; margin-top:4px; }
  .conn .bar > div { height:100%; background:var(--accent); border-radius:999px; }
  .muted { color:rgba(255,255,255,.4); font-size:12px; }
  footer { position:absolute; bottom:12px; left:300px; font-size:11px;
    color:rgba(255,255,255,.6); background:rgba(0,0,0,.4); padding:6px 10px; border-radius:6px; }
</style></head><body>
"""

_BODY_SCRIPT = """
const COLORS = %COLORS%;
function clusterColor(c){ return COLORS[c % COLORS.length]; }
let NETWORK = null, RAW = null, selectedId = null;

function compact(n){
  if (n >= 1e6) return (n/1e6).toFixed(1)+'M';
  if (n >= 1e3) return (n/1e3).toFixed(1)+'K';
  return ''+n;
}

function render(data){
  RAW = data;
  document.getElementById('badge').className = 'badge ' + data.source;
  document.getElementById('badge').textContent =
    data.source === 'brandwatch' ? 'Live Brandwatch' : 'Sample data';
  document.getElementById('stats').textContent =
    `${data.nodes.length} keywords · ${data.edges.length} connections · ${data.meta.totalMentions.toLocaleString()} mentions`;

  const maxM = Math.max(1, ...data.nodes.map(n=>n.mentions));
  const nodes = data.nodes.map(n => ({
    id: n.id, label: n.id,
    value: n.mentions,
    color: { background: clusterColor(n.cluster), border: clusterColor(n.cluster) },
    font: { color: 'rgba(255,255,255,.92)', size: 12 + 14*Math.sqrt(n.mentions/maxM) },
  }));
  const edges = data.edges.map(e => ({
    from: e.source, to: e.target, value: e.strength,
    title: `${e.cooccurrences}× together · strength ${e.strength.toFixed(2)} · pmi ${e.pmi.toFixed(2)}`,
    color: { color: 'rgba(255,255,255,.15)', highlight: 'rgba(255,255,255,.6)' },
  }));

  const container = document.getElementById('graph');
  const options = {
    nodes: { shape: 'dot', scaling: { min: 6, max: 40 }, borderWidth: 0 },
    edges: { scaling: { min: 0.5, max: 8 }, smooth: false },
    physics: { barnesHut: { gravitationalConstant: -3000, springLength: 90, springConstant: 0.03,
      damping: 0.4 }, stabilization: { iterations: 150 } },
    interaction: { hover: true, tooltipDelay: 120 },
  };
  if (NETWORK) NETWORK.destroy();
  NETWORK = new vis.Network(container, { nodes, edges }, options);
  NETWORK.on('click', params => {
    if (params.nodes.length) showDetails(params.nodes[0]);
    else { selectedId = null; document.getElementById('details').innerHTML = detailsEmpty(); }
  });

  const legend = {};
  data.nodes.slice().sort((a,b)=>b.mentions-a.mentions).forEach(n => {
    if (!legend[n.cluster]) legend[n.cluster] = { top:n.id, count:0 };
    legend[n.cluster].count++;
  });
  document.getElementById('legend').innerHTML = Object.entries(legend)
    .sort((a,b)=>b[1].count-a[1].count)
    .map(([c,info]) => `<li><span class="dot" style="background:${clusterColor(+c)}"></span>
      <strong style="color:rgba(255,255,255,.9)">${info.top}</strong>
      <span class="muted">+${info.count-1} more</span></li>`).join('');
}

function detailsEmpty(){ return '<p class="muted">Click a keyword to see its connections.</p>'; }

function showDetails(id){
  selectedId = id;
  const node = RAW.nodes.find(n => n.id === id);
  const conns = RAW.edges
    .filter(e => e.source === id || e.target === id)
    .map(e => ({ other: e.source === id ? e.target : e.source,
                 strength: e.strength, co: e.cooccurrences, llr: e.llr || 0, pmi: e.pmi || 0 }))
    .sort((a,b)=>b.strength-a.strength).slice(0,12);
  const sent = node.sentiment;
  const sentColor = sent > .1 ? '#06d6a0' : sent < -.1 ? '#ff5a7e' : 'inherit';
  const maxInf = Math.max(1e-9, ...RAW.nodes.map(n => n.influence || 0));
  const maxBri = Math.max(1e-9, ...RAW.nodes.map(n => n.bridge || 0));
  document.getElementById('details').innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;">
      <span class="dot" style="background:${clusterColor(node.cluster)}"></span>
      <h2 style="margin:0;font-size:18px;">${node.id}</h2></div>
    <p class="muted" style="margin:4px 0 0;">Community #${node.cluster}</p>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:14px;">
      <div class="stat"><div class="v">${node.mentions.toLocaleString()}</div><div class="k">Mentions</div></div>
      <div class="stat"><div class="v">${compact(node.reach)}</div><div class="k">Reach</div></div>
      <div class="stat"><div class="v" style="color:${sentColor}">${sent>=0?'+':''}${sent.toFixed(2)}</div><div class="k">Sentiment</div></div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:8px;">
      <div class="stat"><div class="v">${Math.round((node.influence||0)/maxInf*100)}</div><div class="k">Influence</div></div>
      <div class="stat"><div class="v">${Math.round((node.bridge||0)/maxBri*100)}</div><div class="k">Bridge</div></div>
    </div>
    <p style="margin:18px 0 6px;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:rgba(255,255,255,.4);font-weight:600;">Strongest connections</p>
    ${conns.map(c => `<div class="conn" title="significance G²=${c.llr.toFixed(0)} · PMI=${c.pmi.toFixed(2)}" onclick="showDetails('${c.other.replace(/'/g,"\\\\'")}');NETWORK.selectNodes(['${c.other.replace(/'/g,"\\\\'")}'])">
        <div style="display:flex;justify-content:space-between;font-size:14px;">
          <span style="font-weight:500;">${c.other}</span>
          <span class="muted">${c.co}× together</span></div>
        <div class="bar"><div style="width:${Math.min(100,c.strength*100)}%"></div></div>
      </div>`).join('') || '<p class="muted">No connections at current thresholds.</p>'}
  `;
}
"""


def _palette_script() -> str:
    return _BODY_SCRIPT.replace("%COLORS%", json.dumps(CLUSTER_COLORS))


def _shell(main_aside: str, extra_script: str) -> str:
    return (
        _HEAD
        + """<header>
  <div style="display:flex;align-items:baseline;gap:12px;">
    <h1><span class="accent">🔥 Social</span> Tinder</h1>
    <span class="sub">keyword chemistry from social listening</span>
  </div>
  <span id="badge" class="badge sample">Sample data</span>
</header>
<div class="layout">
"""
        + main_aside
        + """
  <div id="graph"></div>
  <aside class="right"><div id="details"><p class="muted">Click a keyword to see its connections.</p></div></aside>
</div>
<footer id="stats"></footer>
<script>
"""
        + _palette_script()
        + extra_script
        + """
</script></body></html>"""
    )


def interactive_page() -> str:
    """Full UI with live filter controls; fetches /api/network."""
    aside = """  <aside>
    <div class="field"><label>Search topic</label>
      <input id="f-search" type="text" placeholder="e.g. electric vehicles" />
      <p class="muted" style="margin:4px 0 0;">Used by the live Brandwatch client.</p></div>
    <div class="field"><div class="row"><label>Min. connection strength</label><span class="val" id="v-strength">0.04</span></div>
      <input id="f-strength" type="range" min="0" max="0.4" step="0.01" value="0.04" /></div>
    <div class="field"><div class="row"><label>Min. co-occurrences</label><span class="val" id="v-co">3</span></div>
      <input id="f-co" type="range" min="1" max="30" step="1" value="3" /></div>
    <div class="field"><div class="row"><label>Min. keyword mentions</label><span class="val" id="v-mentions">5</span></div>
      <input id="f-mentions" type="range" min="1" max="50" step="1" value="5" /></div>
    <div class="field"><div class="row"><label>Min. significance (G²)</label><span class="val" id="v-llr">off</span></div>
      <input id="f-llr" type="range" min="0" max="50" step="1" value="0" /></div>
    <div class="field"><div class="row"><label>Max. keywords shown</label><span class="val" id="v-max">80</span></div>
      <input id="f-max" type="range" min="10" max="150" step="5" value="80" /></div>
    <div class="field"><label>Communities</label><ul id="legend" class="legend" style="list-style:none;padding:0;margin:0;"></ul></div>
  </aside>"""

    script = """
async function load(){
  const p = new URLSearchParams({
    minStrength: document.getElementById('f-strength').value,
    minCooccurrences: document.getElementById('f-co').value,
    minMentions: document.getElementById('f-mentions').value,
    minLLR: document.getElementById('f-llr').value,
    maxNodes: document.getElementById('f-max').value,
  });
  const s = document.getElementById('f-search').value.trim();
  if (s) p.set('search', s);
  const res = await fetch('/api/network?' + p.toString());
  render(await res.json());
}
let t = null;
function schedule(){ clearTimeout(t); t = setTimeout(load, 250); }
['f-strength','f-co','f-mentions','f-llr','f-max'].forEach(id => {
  const el = document.getElementById(id);
  const labelMap = { 'f-strength':'v-strength','f-co':'v-co','f-mentions':'v-mentions','f-llr':'v-llr','f-max':'v-max' };
  el.addEventListener('input', () => {
    document.getElementById(labelMap[id]).textContent =
      (id === 'f-llr' && el.value === '0') ? 'off' : el.value;
    schedule();
  });
});
document.getElementById('f-search').addEventListener('input', schedule);
load();
"""
    return _shell(aside, script)


def static_page(network: dict) -> str:
    """Self-contained HTML with the network inlined — no server needed."""
    aside = """  <aside>
    <div class="field"><label>Communities</label><ul id="legend" class="legend" style="list-style:none;padding:0;margin:0;"></ul></div>
    <p class="muted">Static export. Re-run the CLI with different thresholds to change the graph.</p>
  </aside>"""
    script = "\nrender(%DATA%);\n".replace("%DATA%", json.dumps(network))
    return _shell(aside, script)
