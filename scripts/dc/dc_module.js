// ================= DC metro tab =================
(function () {
  const FP = 1.25;                       // Antarctic sea-level fingerprint factor for the Mid-Atlantic
  const ui = id => document.getElementById(id);
  const wrap = ui('dcWrap'), canvas = ui('dcMap'), ctx = canvas.getContext('2d');
  // Phones get a half-resolution base image and 40 m water/building layers to stay within mobile memory limits
  const lite = matchMedia('(pointer: coarse)').matches || Math.min(screen.width, screen.height) < 820;
  let gs = 2;                            // base (10 m) pixels per water-grid cell
  const st = { globalS: 0, fp: true, states: true, loaded: false, visible: false, dirty: true };
  let meta, W, H, flood, base, waterCv, waterCtx, waterImg, dotCv, dotCtx, dotImg;
  let bStart, bSub, bOcc, bNv, bOff, coords, bCell, tileStart;

  async function gunzip(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(url + ' ' + r.status);
    let buf;
    if (url.endsWith('.txt')) { const s = atob((await r.text()).trim()); buf = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) buf[i] = s.charCodeAt(i); }
    else buf = new Uint8Array(await r.arrayBuffer());
    if (buf[0] !== 0x1f || buf[1] !== 0x8b) return buf;      // already decompressed by the server
    const s = new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'));
    return new Uint8Array(await new Response(s).arrayBuffer());
  }
  async function load() {
    try {
      ui('dcLoading').textContent = 'Loading elevation, land cover and 417,042 buildings…';
      const [m, fl, bl, img] = await Promise.all([
        fetch('dc/dc_meta.json').then(r => r.json()),
        gunzip('dc/dc_flood.txt'),
        gunzip('dc/dc_buildings.txt'),
        new Promise((res, rej) => { const im = new Image(); im.onload = () => res(im); im.onerror = rej; im.src = lite ? 'dc/dc_base_lite.webp' : 'dc/dc_base.webp'; })
      ]);
      meta = m; W = m.W; H = m.H; flood = fl; base = img;
      if (lite) {   // collapse the 20 m flood grid to 40 m (lowest flood level of each 2x2 block)
        const W2 = W >> 1, H2 = H >> 1, f2 = new Uint8Array(W2 * H2);
        for (let r = 0; r < H2; r++) for (let c = 0; c < W2; c++) {
          const i = 2 * r * W + 2 * c;
          f2[r * W2 + c] = Math.min(fl[i], fl[i + 1], fl[i + W], fl[i + W + 1]);
        }
        flood = f2; W = W2; H = H2; gs = 4;
      }
      parseBuildings(bl);
      waterCv = document.createElement('canvas'); waterCv.width = W; waterCv.height = H;
      waterCtx = waterCv.getContext('2d'); waterImg = waterCtx.createImageData(W, H);
      dotCv = document.createElement('canvas'); dotCv.width = W; dotCv.height = H;
      dotCtx = dotCv.getContext('2d'); dotImg = dotCtx.createImageData(W, H);
      st.loaded = true; ui('dcLoading').remove();
      legend(); resize(); update();
    } catch (e) {
      ui('dcLoading').textContent = 'Could not load the DC data files (' + e.message + '). They must sit in a "dc" folder next to this page and be served over http(s).';
    }
  }

  function parseBuildings(buf) {
    const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
    const n = meta.bldTotal;
    bStart = new Uint8Array(n); bSub = new Uint8Array(n); bOcc = new Uint8Array(n);
    bNv = new Uint16Array(n); bOff = new Uint32Array(n); bCell = new Int32Array(n);
    let o = 0, k = 0, totalV = 0;
    const tmp = [];
    while (o < buf.length && k < n) {
      bStart[k] = buf[o]; bSub[k] = buf[o + 1]; bOcc[k] = buf[o + 2];
      const nv = dv.getUint16(o + 3, true); bNv[k] = nv;
      tmp.push(o + 5); o += 5 + 8 + (nv - 1) * 4; totalV += nv; k++;
    }
    const count = k;
    coords = new Int32Array(totalV * 2);
    let v = 0;
    for (k = 0; k < count; k++) {
      let p = tmp[k], x = dv.getInt32(p, true), y = dv.getInt32(p + 4, true); p += 8;
      bOff[k] = v; let sx = 0, sy = 0;
      coords[v * 2] = x; coords[v * 2 + 1] = y; sx += x; sy += y; v++;
      for (let i = 1; i < bNv[k]; i++) {
        x += dv.getInt16(p, true); y += dv.getInt16(p + 2, true); p += 4;
        coords[v * 2] = x; coords[v * 2 + 1] = y; sx += x; sy += y; v++;
      }
      // coords are 0.5 m units; flood grid cells are 20 m = 40 units
      const cx = Math.min(W - 1, Math.max(0, Math.floor(sx / bNv[k] / (gs * 20)))), cy = Math.min(H - 1, Math.max(0, Math.floor(sy / bNv[k] / (gs * 20))));
      bCell[k] = cy * W + cx;
    }
    meta.bldCount = count;
    const t = meta.tiles, nt = t.nx * t.ny;
    tileStart = new Uint32Array(nt + 1);
    for (let i = 0; i < nt; i++) tileStart[i + 1] = tileStart[i] + t.counts[i];
  }

  const localRise = () => st.globalS * (st.fp ? FP : 1);

  // ---------- water + building dots ----------
  const depthStops = [[0, [150, 225, 235]], [2, [80, 175, 210]], [10, [40, 115, 175]], [30, [20, 65, 130]], [70, [10, 35, 85]]];
  function depthColor(d) {
    for (let s = 1; s < depthStops.length; s++) if (d <= depthStops[s][0]) {
      const [d0, a] = depthStops[s - 1], [d1, b] = depthStops[s], u = (d - d0) / (d1 - d0);
      return [a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u];
    }
    return depthStops[depthStops.length - 1][1];
  }
  const depthLut = []; for (let i = 0; i <= 200; i++) depthLut.push(depthColor(i * 0.5));
  function computeLayers() {
    const lv = localRise() / 0.5, px = waterImg.data, n = W * H;
    for (let i = 0; i < n; i++) {
      const f = flood[i], p = i * 4;
      if (f > 0 && f !== 255 && f <= lv) {
        const c = depthLut[Math.min(200, Math.round(lv - f))];
        px[p] = c[0]; px[p + 1] = c[1]; px[p + 2] = c[2]; px[p + 3] = 225;
      } else px[p + 3] = 0;
    }
    waterCtx.putImageData(waterImg, 0, 0);
    const dp = dotImg.data; dp.fill(0);
    for (let k = 0; k < meta.bldCount; k++) {
      if (bSub[k] <= lv) continue;
      const p = bCell[k] * 4;
      if (bStart[k] <= lv) { dp[p] = 235; dp[p + 1] = 110; dp[p + 2] = 40; dp[p + 3] = 255; }
      else if (dp[p + 3] === 0) { dp[p] = 45; dp[p + 1] = 50; dp[p + 2] = 58; dp[p + 3] = 200; }
    }
    dotCtx.putImageData(dotImg, 0, 0);
  }

  // ---------- view ----------
  const view = { scale: 1, tx: 0, ty: 0 }; let fit = 1;
  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, lite ? 2 : 3), r = wrap.getBoundingClientRect();
    if (!r.width) return;
    canvas.width = Math.round(r.width * dpr); canvas.height = Math.round(r.height * dpr);
    if (meta) fit = Math.min(canvas.width / meta.baseW, canvas.height / meta.baseH);
    draw();
  }
  const sNow = () => fit * view.scale;           // screen px per 10 m base pixel
  function draw() {
    if (!st.loaded) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = '#cfd6dc'; ctx.fillRect(0, 0, canvas.width, canvas.height);
    const s = sNow(), ox = canvas.width / 2 + view.tx - meta.baseW / 2 * s, oy = canvas.height / 2 + view.ty - meta.baseH / 2 * s;
    ctx.setTransform(s, 0, 0, s, ox, oy);
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(base, 0, 0, meta.baseW, meta.baseH);
    ctx.drawImage(waterCv, 0, 0, W, H, 0, 0, W * gs, H * gs);
    if (s < 0.9) {
      ctx.globalAlpha = 0.85; ctx.drawImage(dotCv, 0, 0, W, H, 0, 0, W * gs, H * gs); ctx.globalAlpha = 1;
    } else drawPolygons(s, ox, oy);
    if (st.states) drawStates(s, ox, oy);
  }
  // state boundaries (Census TIGER) with a white halo, plus labels, drawn at constant screen width
  function drawStates(s, ox, oy) {
    const dpr = canvas.width / canvas.getBoundingClientRect().width, S = meta.states;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    const path = new Path2D();
    for (const line of S.lines) {
      path.moveTo(line[0][0] * s + ox, line[0][1] * s + oy);
      for (let i = 1; i < line.length; i++) path.lineTo(line[i][0] * s + ox, line[i][1] * s + oy);
    }
    ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.strokeStyle = 'rgba(255,255,255,.85)'; ctx.lineWidth = 5 * dpr; ctx.setLineDash([]); ctx.stroke(path);
    ctx.strokeStyle = '#2a2140'; ctx.lineWidth = 2 * dpr; ctx.setLineDash([9 * dpr, 4 * dpr, 2 * dpr, 4 * dpr]); ctx.stroke(path);
    ctx.setLineDash([]);
    if (meta.counties) {   // county and independent-city boundaries: thinner solid lines
      const cp = new Path2D();
      for (const line of meta.counties.lines) {
        cp.moveTo(line[0][0] * s + ox, line[0][1] * s + oy);
        for (let i = 1; i < line.length; i++) cp.lineTo(line[i][0] * s + ox, line[i][1] * s + oy);
      }
      ctx.strokeStyle = 'rgba(255,255,255,.8)'; ctx.lineWidth = 3.5 * dpr; ctx.stroke(cp);
      ctx.strokeStyle = '#7a2e8e'; ctx.lineWidth = 1.4 * dpr; ctx.stroke(cp);
      ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillStyle = '#7a2e8e'; ctx.strokeStyle = 'rgba(255,255,255,.9)';
      for (const [name, x, y, size] of meta.counties.labels) {
        const cssScale = s / dpr;                                  // CSS px per 10 m
        if (cssScale < (size === 2 ? 0.15 : 0.12)) continue;       // names appear once there is room for them
        const sx = x * s + ox, sy = y * s + oy, txt = name.split('').join(String.fromCharCode(8202));
        ctx.font = `600 ${(size === 1 ? 11 : 10) * dpr}px system-ui, sans-serif`; ctx.lineWidth = 3.5 * dpr;
        ctx.strokeText(txt, sx, sy); ctx.fillText(txt, sx, sy);
      }
    }
    ctx.font = `600 ${13 * dpr}px system-ui, sans-serif`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.lineWidth = 4 * dpr; ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.fillStyle = '#2a2140';
    for (const [name, x, y] of S.labels) {
      const sx = x * s + ox, sy = y * s + oy;
      if (sx < 0 || sy < 0 || sx > canvas.width || sy > canvas.height) continue;
      ctx.strokeText(name.split('').join(String.fromCharCode(8202)), sx, sy); ctx.fillText(name.split('').join(String.fromCharCode(8202)), sx, sy);
    }
  }
  function drawPolygons(s, ox, oy) {
    const lv = localRise() / 0.5, t = meta.tiles, tilePx = t.size / 10;
    // visible base-pixel window
    const vx0 = -ox / s, vy0 = -oy / s, vx1 = vx0 + canvas.width / s, vy1 = vy0 + canvas.height / s;
    const tx0 = Math.max(0, Math.floor(vx0 / tilePx) - 1), tx1 = Math.min(t.nx - 1, Math.floor(vx1 / tilePx) + 1);
    const ty0 = Math.max(0, Math.floor(vy0 / tilePx) - 1), ty1 = Math.min(t.ny - 1, Math.floor(vy1 / tilePx) + 1);
    const dry = new Path2D(), wet = [new Path2D(), new Path2D(), new Path2D()];
    const k5 = 0.05; // 0.5 m units -> 10 m base pixels
    for (let ty = ty0; ty <= ty1; ty++) for (let tx = tx0; tx <= tx1; tx++) {
      const tId = ty * t.nx + tx;
      for (let k = tileStart[tId]; k < tileStart[tId + 1]; k++) {
        if (bSub[k] <= lv) continue;
        let path = dry;
        if (bStart[k] <= lv) { const fr = (lv - bStart[k]) / Math.max(1, bSub[k] - bStart[k]); path = wet[Math.min(2, Math.floor(fr * 3))]; }
        let v = bOff[k];
        path.moveTo(coords[v * 2] * k5, coords[v * 2 + 1] * k5);
        for (let i = 1; i < bNv[k]; i++) { v++; path.lineTo(coords[v * 2] * k5, coords[v * 2 + 1] * k5); }
        path.closePath();
      }
    }
    ctx.fillStyle = '#353b44'; ctx.fill(dry);
    ['#f4a340', '#ec6f2d', '#c8381f'].forEach((c, i) => { ctx.fillStyle = c; ctx.fill(wet[i]); });
    if (s > 3) { ctx.lineWidth = 1 / s; ctx.strokeStyle = 'rgba(255,255,255,.35)'; ctx.stroke(dry); }
  }
  function screenToBase(cx, cy) {
    const r = canvas.getBoundingClientRect(), dpr = canvas.width / r.width, s = sNow();
    const sx = (cx - r.left) * dpr, sy = (cy - r.top) * dpr;
    return [(sx - canvas.width / 2 - view.tx) / s + meta.baseW / 2, (sy - canvas.height / 2 - view.ty) / s + meta.baseH / 2];
  }
  function zoomAt(factor, cx, cy) {
    const r = canvas.getBoundingClientRect(), dpr = canvas.width / r.width;
    const sx = (cx - r.left) * dpr - canvas.width / 2, sy = (cy - r.top) * dpr - canvas.height / 2;
    const ns = Math.min(80, Math.max(1, view.scale * factor)), f = ns / view.scale;
    view.tx = sx - (sx - view.tx) * f; view.ty = sy - (sy - view.ty) * f; view.scale = ns;
    if (ns === 1) { view.tx = 0; view.ty = 0; }
    draw();
  }
  wrap.addEventListener('wheel', e => { e.preventDefault(); zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY); }, { passive: false });
  const pointers = new Map(); let pinch = 0, moved = false;
  wrap.addEventListener('pointerdown', e => {
    if (e.target.closest('.mapBtns')) return;
    wrap.setPointerCapture(e.pointerId); pointers.set(e.pointerId, [e.clientX, e.clientY]); moved = false;
    if (pointers.size === 2) { const [a, b] = [...pointers.values()]; pinch = Math.hypot(a[0] - b[0], a[1] - b[1]); }
  });
  wrap.addEventListener('pointermove', e => {
    if (!pointers.has(e.pointerId)) { readout(e.clientX, e.clientY); return; }
    const prev = pointers.get(e.pointerId), dpr = canvas.width / canvas.getBoundingClientRect().width;
    pointers.set(e.pointerId, [e.clientX, e.clientY]);
    if (pointers.size === 1) {
      const dx = e.clientX - prev[0], dy = e.clientY - prev[1];
      if (Math.abs(dx) + Math.abs(dy) > 1) moved = true;
      if (view.scale > 1) { view.tx += dx * dpr; view.ty += dy * dpr; draw(); }
    } else if (pointers.size === 2) {
      moved = true; const [a, b] = [...pointers.values()], d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      zoomAt(d / pinch, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2); pinch = d;
    }
  });
  const endP = e => { if (pointers.has(e.pointerId) && !moved && pointers.size === 1) readout(e.clientX, e.clientY); pointers.delete(e.pointerId); };
  wrap.addEventListener('pointerup', endP); wrap.addEventListener('pointercancel', endP);
  wrap.addEventListener('pointerleave', () => { if (!pointers.size) ui('dcReadout').style.display = 'none'; });
  ui('dcZoomIn').onclick = () => { const r = canvas.getBoundingClientRect(); zoomAt(1.8, r.left + r.width / 2, r.top + r.height / 2); };
  ui('dcZoomOut').onclick = () => { const r = canvas.getBoundingClientRect(); zoomAt(1 / 1.8, r.left + r.width / 2, r.top + r.height / 2); };
  ui('dcZoomReset').onclick = () => { view.scale = 1; view.tx = 0; view.ty = 0; draw(); };
  window.addEventListener('resize', () => { if (st.visible) resize(); });

  // ---------- readout ----------
  function utmToLatLon(E, N) { // UTM zone 18N, WGS84/NAD83
    const a = 6378137, f = 1 / 298.257223563, e2 = f * (2 - f), ep2 = e2 / (1 - e2), k0 = 0.9996;
    const x = E - 500000, M = N / k0, mu = M / (a * (1 - e2 / 4 - 3 * e2 * e2 / 64));
    const e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2));
    const p1 = mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * Math.sin(2 * mu) + (21 * e1 * e1 / 16) * Math.sin(4 * mu) + (151 * e1 ** 3 / 96) * Math.sin(6 * mu);
    const C1 = ep2 * Math.cos(p1) ** 2, T1 = Math.tan(p1) ** 2, N1 = a / Math.sqrt(1 - e2 * Math.sin(p1) ** 2);
    const R1 = a * (1 - e2) / (1 - e2 * Math.sin(p1) ** 2) ** 1.5, D = x / (N1 * k0);
    const lat = p1 - (N1 * Math.tan(p1) / R1) * (D * D / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * ep2) * D ** 4 / 24);
    const lon = (D - (1 + 2 * T1 + C1) * D ** 3 / 6) / Math.cos(p1);
    return [lat * 180 / Math.PI, -75 + lon * 180 / Math.PI];
  }
  function readout(cx, cy) {
    const el = ui('dcReadout'); if (!st.loaded) return;
    const [bx, by] = screenToBase(cx, cy);
    if (bx < 0 || by < 0 || bx >= meta.baseW || by >= meta.baseH) { el.style.display = 'none'; return; }
    const c = Math.min(W - 1, Math.floor(bx / gs)), r = Math.min(H - 1, Math.floor(by / gs)), f = flood[r * W + c];
    const [lat, lon] = utmToLatLon(meta.x0 + bx * 10, meta.y0 - by * 10);
    let txt;
    if (f === 0) txt = 'Water today (river or bay)';
    else if (f === 255) txt = 'Stays dry even at full melt';
    else {
      const need = f * 0.5, g = need / (st.fp ? FP : 1), pct = window.antarctica.meltForGlobalRise(g);
      txt = `Floods at <b>${need.toFixed(1)} m</b> local rise` + (pct == null ? ' (more than Antarctica alone can supply)' : ` ≈ <b>${pct.toFixed(0)}%</b> of Antarctic ice melted`);
      txt += localRise() >= need ? `<br>Under ${(localRise() - need).toFixed(1)} m of water now` : '';
    }
    el.innerHTML = `${lat.toFixed(4)}°N, ${Math.abs(lon).toFixed(4)}°W<br>${txt}`;
    el.style.display = 'block';
  }

  // ---------- stats & legend ----------
  function interp(arr, L) { const x = Math.min(arr.length - 1, L / 0.5), i = Math.floor(x), u = x - i; return i >= arr.length - 1 ? arr[arr.length - 1] : arr[i] + (arr[i + 1] - arr[i]) * u; }
  const fmt = v => Math.round(v).toLocaleString();
  function stats() {
    const L = localRise();
    ui('dcRise').textContent = L.toFixed(1) + ' m';
    const a = meta.areaKm2; let land = 0, dev = 0, green = 0;
    const rows = [];
    for (const k in a) { const v = interp(a[k], L); land += v; if (+k >= 21 && +k <= 24) dev += v; if ([41, 42, 43, 90, 95].includes(+k)) green += v; if (v > 0.05) rows.push([meta.nlcdNames[k], v, meta.nlcdPal[k]]); }
    ui('dcLand').textContent = land.toFixed(0) + ' km²';
    ui('dcDev').textContent = dev.toFixed(0) + ' km²';
    ui('dcBTouch').textContent = fmt(interp(meta.bld.start, L));
    ui('dcBSub').textContent = fmt(interp(meta.bld.sub, L));
    ui('dcGreen').textContent = green.toFixed(0) + ' km²';
    rows.sort((x, y) => y[1] - x[1]);
    ui('dcLcRows').innerHTML = rows.slice(0, 6).map(([n, v, c]) => `<div class="row"><span class="sw" style="background:rgb(${c})"></span><span style="flex:1">${n}</span><b>${v.toFixed(1)} km²</b></div>`).join('') || '<div class="note">Nothing flooded yet.</div>';
    const occ = Object.entries(meta.bldOcc).map(([n, o]) => [n, interp(o.sub, L)]).filter(x => x[1] >= 1).sort((x, y) => y[1] - x[1]);
    ui('dcOccRows').innerHTML = occ.slice(0, 6).map(([n, v]) => `<div class="row"><span style="flex:1">${n}</span><b>${fmt(v)}</b></div>`).join('') || '<div class="note">None yet.</div>';
  }
  function legend() {
    const ramp = 'linear-gradient(90deg,' + depthStops.map(([d, c]) => `rgb(${c.map(Math.round)}) ${(d / 70 * 100).toFixed(0)}%`).join(',') + ')';
    const sw = (c, l) => `<div class="row"><span class="sw" style="background:${c}"></span>${l}</div>`;
    const lc = [[21, 'Developed (open → high intensity)'], [41, 'Forest'], [81, 'Pasture & crops'], [90, 'Wetlands'], [11, "Today's rivers & bay"]];
    ui('dcLegend').innerHTML =
      `<div>New flood water, by depth<div class="ramp" style="background:${ramp}"></div><div class="rampLbl"><span>0 m</span><span>35</span><span>70 m</span></div></div>` +
      `<div class="row"><span class="sw" style="background:repeating-linear-gradient(90deg,#2a2140 0 6px,#fff 6px 8px);height:4px;border:0"></span>State boundary</div>` +
      `<div class="row"><span class="sw" style="background:#7a2e8e;height:3px;border:0"></span>County / city boundary</div>` +
      sw('#353b44', 'Building, dry') + sw('#f4a340', 'Building, water at the walls') + sw('#c8381f', 'Building, nearly submerged') +
      `<div class="note" style="margin:2px 0">Fully submerged buildings disappear. Individual footprints appear when you zoom in.</div>` +
      lc.map(([k, l]) => sw(`rgb(${meta.nlcdPal[k]})`, l)).join('');
  }

  let pending = false;
  function update() {
    if (!st.loaded) return;
    if (!st.visible) { st.dirty = true; return; }
    if (pending) return; pending = true;
    requestAnimationFrame(() => { pending = false; st.dirty = false; computeLayers(); draw(); stats(); });
  }
  window.addEventListener('meltchange', e => { st.globalS = e.detail.S; update(); });
  ui('fpToggle').addEventListener('change', e => { st.fp = e.target.checked; st.dirty = true; update(); });
  ui('stateToggle').addEventListener('change', e => { st.states = e.target.checked; draw(); });
  window.dcMap = {
    show() { st.visible = true; if (!st.loaded && !st.started) { st.started = true; load(); } resize(); if (st.dirty) update(); },
    hide() { st.visible = false; },
    resize() { if (st.visible) resize(); }
  };
})();
