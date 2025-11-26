import os
import sys
import json


def _root():
    return os.path.dirname(os.path.dirname(__file__))


def _artifacts_dir(domain: str) -> str:
    return os.path.join(_root(), "artifacts", domain)


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _detect_mode(artifact_dir: str, base: str | None):
    merged = os.path.join(artifact_dir, "taxonomy_seeds.merged.json")
    if base:
        return "single"
    if os.path.exists(merged):
        return "merged"
    return "single"


def _paths_to_hierarchy(paths: list) -> dict:
    trie = {}
    for p in paths or []:
        segs = p.get("path") or []
        cur = trie
        for s in segs:
            s = str(s or "").strip()
            if not s:
                continue
            cur = cur.setdefault(s, {})

    def conv(node: dict, name: str = "root") -> dict:
        children = []
        for k, v in node.items():
            children.append(conv(v, k))
        return {"name": name, "children": children}

    return conv(trie, "root")


def _build_html(domain: str, base: str, seeds: dict, out_json_name: str) -> str:
    payload = {
        "domain": domain,
        "base": base,
        "levels": seeds.get("levels", []),
        "paths": seeds.get("paths", []),
        "out_json": out_json_name,
    }
    mind = (
        _paths_to_hierarchy(payload["paths"])
        if isinstance(payload.get("paths"), list)
        else {"name": "root", "children": []}
    )
    j = json.dumps(payload, ensure_ascii=False)
    m = json.dumps(mind, ensure_ascii=False)
    tpl = """<!doctype html><html><head><meta charset=\"utf-8\"><title>Review (D3 Radial Tree)</title>
<style>
:root{--bg:#f7f7fb;--card:#ffffff;--border:#e5e7eb;--text:#111827;--muted:#6b7280;--primary:#2563eb}
html,body{background:var(--bg);color:var(--text)}
body{font-family:system-ui,Segoe UI,Arial;line-height:1.6;margin:0}
.hdr{display:flex;gap:12px;align-items:center;padding:12px 16px;border-bottom:1px solid var(--border);background:var(--card)}
.hdr h2{margin:0;font-size:16px}
.meta{color:var(--muted);font-size:13px}
.mindwrap{height:55vh;background:var(--card);border:1px solid var(--border);border-radius:12px;margin:12px;overflow:hidden}
.mindwrap svg{width:100%;height:100%}
.panel{background:var(--card);border:1px solid var(--border);border-radius:12px;margin:12px;padding:12px}
.tabs{display:flex;gap:8px;margin:0 12px}
.tab{padding:8px 12px;border:1px solid var(--border);border-radius:8px;background:var(--card);cursor:pointer}
.tab.active{border-color:var(--primary);background:#eef4ff}
.row{display:flex;gap:12px;flex-wrap:wrap}
select{padding:8px 10px;border:1px solid var(--border);border-radius:8px;background:#fff}
.link{stroke:#cbd5e1;stroke-width:1;fill:none}
.node text{font-size:12px;fill:#111827;pointer-events:none}
.chip{background:#f3f4f6;border:1px solid var(--border);border-radius:999px;padding:4px 10px;font-size:12px;color:var(--muted);display:inline-block}
.items .item{display:flex;gap:8px;align-items:center;margin:6px 0}
button{padding:8px 12px;border:1px solid var(--border);border-radius:8px;background:#fff;cursor:pointer}
button.primary{border-color:var(--primary);color:var(--primary)}
.tooltip{position:fixed;background:#111827;color:#fff;border-radius:8px;padding:8px 10px;box-shadow:0 8px 24px rgba(0,0,0,0.12);font-size:12px;display:none;pointer-events:none;z-index:9999}
</style>
<script src=\"https://unpkg.com/d3@7/dist/d3.min.js\"></script>
</head><body>
<div class=\"hdr\"><h2>审阅</h2><div class=\"meta\" id=\"meta\"></div><div class=\"meta\" id=\"layoutStatus\">布局:D3 Tree</div><div><button id=\"save\" class=\"primary\">保存 reviewed JSON</button></div></div>
<div class=\"mindwrap\"><div id=\"mind-container\"></div></div>
<div class=\"panel\"><div id=\"levels\"></div><div style=\"margin-top:6px\"><span class=\"chip\" id=\"stats\"></span></div></div>
<div class=\"tabs\"><div class=\"tab active\" id=\"tabBrowse\">浏览分类</div><div class=\"tab\" id=\"tabEdit\">编辑条目</div></div>
<div class=\"panel\" id=\"browse\">
  <div class=\"row\">
    <div><label>一级</label><br/><select id=\"sel0\"><option value=\"\">(全部)</option></select></div>
    <div><label>二级</label><br/><select id=\"sel1\"><option value=\"\">(全部)</option></select></div>
    <div><label>三级</label><br/><select id=\"sel2\"><option value=\"\">(全部)</option></select></div>
    <div><label>四级</label><br/><select id=\"sel3\"><option value=\"\">(全部)</option></select></div>
  </div>
  <div id=\"browseList\"></div>
</div>
<div class=\"panel\" id=\"editPanel\" style=\"display:none\">
  <div id=\"editPath\"></div>
  <div class=\"items\" id=\"editItems\"></div>
  <div><input type=\"text\" id=\"newItem\" placeholder=\"新增item\" /> <button id=\"addItem\">添加</button></div>
</div>
<div id=\"tooltip\" class=\"tooltip\"></div>
<script type=\"application/json\" id=\"stateData\">__STATE__</script>
<script type=\"application/json\" id=\"mindData\">__MIND__</script>
<script>
const state = JSON.parse(document.getElementById('stateData').textContent);
const mindData = JSON.parse(document.getElementById('mindData').textContent);
document.getElementById('meta').textContent = state.domain + ' / ' + state.base;
document.getElementById('levels').innerHTML = '<b>levels:</b> ' + (state.levels||[]).map(x=>x.code||x).join(' / ');
const tip=document.getElementById('tooltip');
const sel0=document.getElementById('sel0');
const sel1=document.getElementById('sel1');
const sel2=document.getElementById('sel2');
const sel3=document.getElementById('sel3');
const stats=document.getElementById('stats');
const browseList=document.getElementById('browseList');
const editPath=document.getElementById('editPath');
const editItems=document.getElementById('editItems');
const newItem=document.getElementById('newItem');
const addItem=document.getElementById('addItem');
const tabBrowse=document.getElementById('tabBrowse');
const tabEdit=document.getElementById('tabEdit');
const panelBrowse=document.getElementById('browse');
const panelEdit=document.getElementById('editPanel');
function activate(tab){ if(tab==='browse'){ tabBrowse.classList.add('active'); tabEdit.classList.remove('active'); panelBrowse.style.display='block'; panelEdit.style.display='none'; } else { tabEdit.classList.add('active'); tabBrowse.classList.remove('active'); panelEdit.style.display='block'; panelBrowse.style.display='none'; } }
tabBrowse.addEventListener('click', function(){ activate('browse'); });
tabEdit.addEventListener('click', function(){ activate('edit'); });
function segsOf(p){return Array.isArray(p.path)?p.path:[]}
function uniqueAtDepth(prefix, depth){ const out=new Set(); for(const p of (state.paths||[])){ const s=segsOf(p); let ok=true; for(let i=0;i<prefix.length;i++){ if((prefix[i]||'')!== (s[i]||'')) { ok=false; break; } } if(!ok) continue; if(depth < s.length){ const v=s[depth]||''; if(v) out.add(v); } } return Array.from(out); }
function pathsByPrefix(prefix){ const out=[]; for(const p of (state.paths||[])){ const s=segsOf(p); let ok=true; for(let i=0;i<prefix.length;i++){ if((prefix[i]||'')!== (s[i]||'')) { ok=false; break; } } if(ok) out.push(p); } return out; }
function fillSelect(sel, opts){ const cur=sel.value; sel.innerHTML='<option value="">(全部)</option>' + (opts||[]).map(o=>'<option>'+o+'</option>').join(''); if(cur && (opts||[]).includes(cur)) sel.value=cur; else sel.value=''; }
function refreshSelectors(){ const v0=sel0.value||''; const v1=sel1.value||''; const v2=sel2.value||''; fillSelect(sel0, uniqueAtDepth([],0)); fillSelect(sel1, uniqueAtDepth(v0? [v0]:[],1)); fillSelect(sel2, uniqueAtDepth(v0? [v0, v1].filter(Boolean):[],2)); fillSelect(sel3, uniqueAtDepth(v0? [v0, v1, v2].filter(Boolean):[],3)); }
function renderBrowse(){ refreshSelectors(); const prefix=[sel0.value||'', sel1.value||'', sel2.value||'', sel3.value||''].filter(x=>x); const arr=pathsByPrefix(prefix); stats.textContent='路径数: '+arr.length; browseList.innerHTML=''; arr.forEach((p,idx)=>{ const wrap=document.createElement('div');wrap.className='panel'; const segs=segsOf(p).map(s=>'<span class="chip">'+s+'</span>').join(' '); const items=(p.items||[]).map(it=>'<div class="item"><span>'+it+'</span></div>').join(''); wrap.innerHTML='<div class="chips">'+segs+'</div><div class="items">'+items+'</div>'; wrap.addEventListener('click',()=>{ selectForEdit(p); activate('edit'); }); browseList.appendChild(wrap); }); }
function selectForEdit(p){ editPath.innerHTML='<div class="chips">'+segsOf(p).map(s=>'<span class="chip">'+s+'</span>').join(' ')+'</div>'; editItems.innerHTML=''; const idx=(state.paths||[]).indexOf(p); (p.items||[]).forEach((it,j)=>{ const row=document.createElement('div');row.className='item'; row.innerHTML='<input type="text" data-kind="item" data-idx="'+idx+'" data-sub="'+j+'" value="'+(it||'')+'" /> <button class="primary" data-kind="delItem" data-idx="'+idx+'" data-sub="'+j+'">删除</button>'; editItems.appendChild(row); }); addItem.onclick=()=>{ const v=(newItem.value||'').trim(); if(!v) return; p.items=p.items||[]; p.items.push(v); newItem.value=''; selectForEdit(p); }; editItems.onclick=(e)=>{ const k=e.target.getAttribute('data-kind'); if(!k) return; const i=parseInt(e.target.getAttribute('data-idx')||'-1'); const j=parseInt(e.target.getAttribute('data-sub')||'-1'); if(k==='delItem' && j>=0){ const arr=state.paths[i].items||[]; arr.splice(j,1); state.paths[i].items=arr; selectForEdit(state.paths[i]); } }; editItems.oninput=(e)=>{ const k=e.target.getAttribute('data-kind'); if(!k) return; const i=parseInt(e.target.getAttribute('data-idx')||'-1'); const j=parseInt(e.target.getAttribute('data-sub')||'-1'); const v=(e.target.value||'').trim(); if(i>=0 && j>=0){ const arr=state.paths[i].items||[]; arr[j]=v; state.paths[i].items=arr; } }; }
sel0.onchange=renderBrowse; sel1.onchange=renderBrowse; sel2.onchange=renderBrowse; sel3.onchange=renderBrowse;
function measurer(text){ const canvas=document.createElement('canvas'); const ctx=canvas.getContext('2d'); ctx.font='12px Segoe UI, Arial'; return Math.max(80, ctx.measureText(String(text||'')).width + 20); }
function depthColor(d){ const arr=['#2563eb','#10b981','#f59e0b','#a78bfa','#ef4444']; return arr[d%arr.length]; }
function renderMindMap(containerId, data){
  const container=document.getElementById(containerId);
  // 清理旧渲染（支持重新渲染）
  container.innerHTML = '';
  const w=Math.max(600, container.clientWidth||window.innerWidth);
  const h=Math.max(600, container.clientHeight||Math.floor(window.innerHeight*0.6));
  const svg = d3.select(container).append('svg').attr('width', w).attr('height', h);
  // group 的初始 transform 我们把 translate 置为中心点，并通过 zoom 修改 transform.x/transform.y/scale
  const g = svg.append('g').attr('transform', `translate(${w/2},${h/2})`);

  // zoom: 我们将变换应用到 g 上，但保留以视图中心为基准
  const zoom = d3.zoom().scaleExtent([0.3, 3]).on('zoom', (ev)=>{
    g.attr('transform', `translate(${ev.transform.x + w/2}, ${ev.transform.y + h/2}) scale(${ev.transform.k})`);
  });
  svg.call(zoom);

  const baseRadius = Math.min(w, h) * 0.42;
  const tree = d3.tree().size([Math.PI*2, baseRadius]).separation((a,b)=> (a.parent === b.parent ? 1 : 1.5));

  // 构造 root，并把初始状态设为收起（把 children 放入 _children）
  const root = d3.hierarchy(data);
  root.each(d => {
    // 创建稳定唯一 key：用从根到当前的路径（不包含 root 名称）
    const path = d.ancestors().reverse().map(n => n.data.name).filter(n => n && n !== 'root').join('|');
    d.data.__key = path || ('root');
  });
  root.x0 = 0; root.y0 = 0;
  root.each(d => {
    if (d.depth >= 1 && d.children) {
      d._children = d.children;
      d.children = null;
    }
  });

  const linkRadial = d3.linkRadial().angle(d => d.x).radius(d => d.y);

  // measurer 保留（canvas 文本测量）
  function measurer(text){
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    ctx.font = '12px Segoe UI, Arial';
    return Math.max(80, ctx.measureText(String(text||'')).width + 20);
  }

  function depthColor(d){ const arr=['#2563eb','#10b981','#f59e0b','#a78bfa','#ef4444']; return arr[d%arr.length]; }

  // ---- 简化且更稳定的按层半径计算 ----
  function computeRadii(root){
    const maxDepth = root.height || 0;
    const step = baseRadius / Math.max(1, maxDepth + 1); // 基础层间距
    // 统计每层最大文本宽度
    const maxWByDepth = new Array(maxDepth+1).fill(0);
    root.descendants().forEach(d => {
      const wtxt = measurer(d.data.name);
      maxWByDepth[d.depth] = Math.max(maxWByDepth[d.depth] || 0, wtxt);
    });
    // radii[d] = d * step + cumulative extra based on maxW
    const radii = new Array(maxDepth+1).fill(0);
    let accExtra = 0;
    for (let d = 0; d <= maxDepth; d++){
      // 每层需要的半径补偿为 maxW / 2 + margin
      const extra = (maxWByDepth[d]||0)/2 + 12;
      // ensure monotonic increase
      accExtra = Math.max(accExtra, extra);
      radii[d] = d * step + accExtra;
      // small growth for spacing
      accExtra = accExtra * 0.9; // decay so deeper layers don't blow up
    }
    return radii;
  }

  // update 函数，使用稳定 key（d.data.__key）
  function update(source){
    // 计算树布局坐标（x: angle, y: radius）
    tree(root);
    // 计算每层的半径并赋值给 d.y
    const radii = computeRadii(root);
    root.each(d => {
      d.y = radii[d.depth] || 0;
    });

    // LINKS
    const links = root.links();
    const linkSel = g.selectAll('path.link').data(links, d => d.target.data.__key);
    // enter
    linkSel.enter().append('path')
      .attr('class', 'link')
      .attr('d', d => linkRadial({ source: { x: source.x0||0, y: source.y0||0 }, target: { x: source.x0||0, y: source.y0||0 } }))
      .attr('stroke', '#cbd5e1').attr('stroke-width', 1).attr('fill', 'none')
      .transition().duration(280)
      .attr('d', d => linkRadial(d));
    // update
    linkSel.transition().duration(280)
      .attr('d', d => linkRadial(d));
    // exit
    linkSel.exit().transition().duration(200).style('opacity',0).remove();

    // NODES (key 使用 __key 保证唯一)
    const nodes = root.descendants();
    const nodeSel = g.selectAll('g.node').data(nodes, d => d.data.__key);

    // enter
    const nodeEnter = nodeSel.enter().append('g')
      .attr('class','node')
      // 起始位置放在 source 的旧位置（用于动画）
      .attr('transform', d => {
        const p = d3.pointRadial(source.x0 || 0, source.y0 || 0);
        return `translate(${p[0]},${p[1]})`;
      })
      .style('opacity', 0)
      .on('click', (ev, d) => {
        if (ev.ctrlKey) {
          const segs = d.ancestors().reverse().map(x=>x.data.name).filter(x=>x && x!=='root');
          sel0.value = segs[0]||'';
          sel1.value = segs[1]||'';
          sel2.value = segs[2]||'';
          sel3.value = segs[3]||'';
          renderBrowse();
          const matched = pathsByPrefix(segs);
          if (matched.length) { selectForEdit(matched[0]); activate('edit'); } else { activate('browse'); }
          return;
        }
        if (d.children) { d._children = d.children; d.children = null; }
        else { d.children = d._children; d._children = null; }
        update(d);
      })
      .on('mousemove', (ev,d) => {
        tip.style.display='block';
        tip.innerHTML = '<div>' + d.ancestors().reverse().map(x=>x.data.name).join(' / ') + '</div><div>层级: ' + d.depth + '</div>';
        tip.style.left = (ev.pageX + 12) + 'px';
        tip.style.top = (ev.pageY - 10) + 'px';
      })
      .on('mouseleave', ()=> { tip.style.display='none'; });

    // 计算并缓存 rect 宽度
    nodeEnter.each(function(d){
      d._rectW = measurer(d.data.name);
    });

    nodeEnter.append('rect')
      .attr('x', d => -d._rectW/2)
      .attr('y', -18)
      .attr('width', d => d._rectW)
      .attr('height', 36)
      .attr('rx', 8)
      .attr('fill', d => d3.color(depthColor(d.depth)).copy({opacity: 0.14}))
      .attr('stroke', d => depthColor(d.depth));

    nodeEnter.append('text')
      .attr('text-anchor','start')
      .attr('x', d => -d._rectW/2 + 8)
      .attr('y', 5)
      .text(d => d.data.name);

    // transition enter to its new position
    nodeEnter.transition().duration(280)
      .style('opacity', 1)
      .attr('transform', d => {
        const p = d3.pointRadial(d.x, d.y);
        return `translate(${p[0]},${p[1]})`;
      });

    // update existing nodes -> move to new positions
    nodeSel.transition().duration(280)
      .attr('transform', d => {
        const p = d3.pointRadial(d.x, d.y);
        return `translate(${p[0]},${p[1]})`;
      });

    // exit nodes
    nodeSel.exit().transition().duration(200).style('opacity', 0).remove();

    // toggles (＋/−)
    const toggles = g.selectAll('text.toggle').data(nodes.filter(d => d.children || d._children), d => d.data.__key);
    toggles.enter().append('text')
      .attr('class','toggle')
      .attr('font-size', 14)
      .attr('font-weight', 'bold')
      .attr('fill', d => depthColor(d.depth))
      .attr('text-anchor','end')
      .text(d => d._children ? '＋' : '−')
      .attr('transform', d => {
        const p = d3.pointRadial(d.x, d.y);
        return `translate(${p[0]},${p[1]})`;
      })
      .attr('x', d => d._rectW/2 - 14)
      .attr('y', 5)
      .style('opacity', 0)
      .transition().duration(280).style('opacity', 1);

    toggles.transition().duration(280)
      .attr('transform', d => {
        const p = d3.pointRadial(d.x, d.y);
        return `translate(${p[0]},${p[1]})`;
      })
      .text(d => d._children ? '＋' : '−');

    toggles.exit().transition().duration(200).style('opacity', 0).remove();

    // 保存坐标供下一次动画使用
    root.each(d => { d.x0 = d.x; d.y0 = d.y; });
  } // end update

  // initial draw
  update(root);

  // expose update in case external code wants to reflow
  window.__lastMindRoot = root;
  window.__lastMindUpdate = update;
}

window.renderBrowse = renderBrowse;
renderBrowse();
(function(){
  function loadD3Seq(urls, cb){ var i=0; function next(){ if(i>=urls.length) return cb(false); var s=document.createElement('script'); s.src=urls[i++]; s.onload=function(){ cb(true); }; s.onerror=function(){ next(); }; document.head.appendChild(s); } next(); }
  var statusEl=document.getElementById('layoutStatus');
  function setStatus(t){ if(statusEl) statusEl.textContent=t; }
  if(window.d3){ setStatus('布局:D3 Tree'); renderMindMap('mind-container', mindData); }
  else {
    setStatus('布局:加载D3中');
    loadD3Seq([
      'https://unpkg.com/d3@7/dist/d3.min.js',
      'https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js',
      'https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js'
    ], function(ok){ if(ok){ setStatus('布局:D3 Tree'); renderMindMap('mind-container', mindData); } else { setStatus('布局:未加载D3，仅列表可用'); } });
  }
})();
function exportJson(){ const out={levels:state.levels,paths:[]}; for(let i=0;i<(state.paths||[]).length;i++){ const p=state.paths[i]; const segs=Array.isArray(p.path)?p.path:[]; const items=Array.isArray(p.items)?p.items.filter(x=>String(x||'').trim().length>0):[]; const entry={path:segs}; if(items.length>0){entry.items=items;} out.paths.push(entry);} const blob=new Blob([JSON.stringify(out,null,2)],{type:'application/json'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=state.out_json||'taxonomy_seeds.reviewed.json'; document.body.appendChild(a); a.click(); URL.revokeObjectURL(a.href); a.remove(); }
document.getElementById('save').addEventListener('click', exportJson);
</script>
</body></html>"""
    return tpl.replace("__STATE__", j).replace("__MIND__", m)


def main():
    root = _root()
    if len(sys.argv) < 2:
        print("usage: python src/review_presenter_d3.py <domain> [<base>]")
        return
    domain = sys.argv[1].strip()
    base = sys.argv[2].strip() if len(sys.argv) > 2 else ""
    artifact_dir = _artifacts_dir(domain)
    os.makedirs(artifact_dir, exist_ok=True)
    mode = _detect_mode(artifact_dir, base if base else None)
    if mode == "merged":
        seeds_path = os.path.join(artifact_dir, "taxonomy_seeds.merged.json")
        out_dir = os.path.join(artifact_dir, "review")
        os.makedirs(out_dir, exist_ok=True)
        out_html = os.path.join(out_dir, "taxonomy_seeds.merged.d3.review.html")
        out_json = "taxonomy_seeds.reviewed.json"
        seeds = _load_json(seeds_path)
        html = _build_html(domain, "taxonomy_seeds.merged", seeds, out_json)
        with open(out_html, "w", encoding="utf-8") as fp:
            fp.write(html)
        print(out_html)
    else:
        if not base:
            files = [
                f
                for f in os.listdir(artifact_dir)
                if f.endswith(".taxonomy_seeds.json")
            ]
            if not files:
                print("no seeds found")
                return
            base = files[0].replace(".taxonomy_seeds.json", "")
        seeds_path = os.path.join(artifact_dir, f"{base}.taxonomy_seeds.json")
        seeds = _load_json(seeds_path)
        out_dir = os.path.join(artifact_dir, "review")
        os.makedirs(out_dir, exist_ok=True)
        out_html = os.path.join(out_dir, f"{base}.d3.review.html")
        out_json = f"{base}.taxonomy_seeds.reviewed.json"
        html = _build_html(domain, base, seeds, out_json)
        with open(out_html, "w", encoding="utf-8") as fp:
            fp.write(html)
        print(out_html)


if __name__ == "__main__":
    main()
