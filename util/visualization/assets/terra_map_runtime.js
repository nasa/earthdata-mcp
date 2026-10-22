// terra-map runtime for map cards.
//
// Reads the card spec from the JSON script element #map-spec, waits for the
// terra-map element, then adds each layer through terraMap.addLayer().
// This file is inlined into a script element, so it must never contain an
// HTML comment opener or a script open/close tag, not even in comments
// (tests/utils/visualization/test_cards.py enforces this).
// The spec is data only: nothing from it is evaluated as code or written as HTML.
//
// Works with @nasa-terra/components 0.0.202, which has addLayer/fitToExtent and
// the terra-map-pointer-move event but not the declarative `layers` attribute.
// Layers are built with the separately loaded OpenLayers UMD build (window.ol)
// and handed to terra's own OL map instance. GeoTIFFs are decoded once with
// geotiff.js and drawn through ol.source.ImageCanvas (no WebGL, no image URLs).

(async () => {
  const spec = JSON.parse(document.getElementById('map-spec').textContent);
  const el = document.getElementById('map');
  const legend = document.getElementById('legend');
  const statusEl = document.getElementById('status');
  const readout = document.getElementById('readout');

  const notes = [];
  const note = (msg, level = 'warn') => {
    notes.push(msg);
    (level === 'info' ? console.info : level === 'error' ? console.error : console.warn)('[map-card]', msg);
    if (level !== 'info') statusEl.classList.add('problem'); // info-only notes stay neutral
    statusEl.hidden = false;
    statusEl.textContent = notes.join('\n');
  };
  window.addEventListener('error', (e) => note(`Script error: ${e.message}`, 'error'));
  window.addEventListener('unhandledrejection', (e) => note(`Unhandled error: ${e.reason}`, 'error'));

  if (!window.ol || !window.ol.source || !window.ol.source.ImageCanvas) {
    return note('OpenLayers failed to load (blocked by the host CSP?)', 'error');
  }

  await customElements.whenDefined('terra-map');
  await el.updateComplete; // terra creates its map service in firstUpdated; addLayer is a no-op before that
  if (typeof el.addLayer !== 'function') {
    return note('terra-map loaded without addLayer(); unsupported terra-ui version', 'error');
  }

  // ------------------------------------------------------------------ helpers
  const clampLat = (ext) => [ext[0], Math.max(ext[1], -85), ext[2], Math.min(ext[3], 85)];
  const unwrap = ([w, s, e, n]) => [w, s, e < w ? e + 360 : e, n]; // antimeridian-crossing boxes
  const fitGeographic = (bounds) =>
    el.fitToExtent(clampLat(unwrap(bounds)), { projection: 'EPSG:4326', padding: [30, 30, 30, 30] });
  const rgb = (c) => `rgb(${c[0]},${c[1]},${c[2]})`;
  const fmt = (v) => {
    if (!Number.isFinite(v)) return '–';
    const a = Math.abs(v);
    return a !== 0 && (a >= 1e5 || a < 1e-3) ? v.toExponential(2) : String(+v.toFixed(a >= 100 ? 1 : 3));
  };

  function legendRow(layer, olLayer) {
    const row = document.createElement('div');
    row.className = 'legend-row';
    const label = document.createElement('label');
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = layer.visible;
    box.addEventListener('change', () => olLayer.setVisible(box.checked));
    const text = document.createElement('span');
    text.textContent = layer.title || layer.name;
    label.append(box, text);
    row.append(label);
    legend.append(row);
    legend.hidden = false;
    return row;
  }

  function colorBar(row, colors, vmin, vmax, units) {
    const bar = document.createElement('div');
    bar.className = 'colorbar';
    bar.style.background = `linear-gradient(to right, ${colors.map(rgb).join(',')})`;
    const ticks = document.createElement('div');
    ticks.className = 'ticks';
    const lo = document.createElement('span');
    const hi = document.createElement('span');
    lo.textContent = fmt(vmin);
    hi.textContent = `${fmt(vmax)}${units ? ' ' + units : ''}`;
    ticks.append(lo, hi);
    row.append(bar, ticks);
  }

  // Integer fill sentinels that often appear without a GDAL_NODATA tag.
  const INT_MIN = { 8: -128, 16: -32768, 32: -2147483648 };
  // Largest file we'll pull into memory when the server ignores Range requests.
  const MAX_FULL_DOWNLOAD = 250 * 1024 * 1024;
  // Longest side of the rendered image. Bigger rasters are read from an overview / resampled.
  const MAX_RENDER = 4096;

  function base64ToBlob(b64) {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new Blob([bytes]);
  }

  async function blobToTiff(blob) {
    // A TIFF starts with "II" or "MM"; anything else is usually a login or error page.
    const head = new Uint8Array(await blob.slice(0, 160).arrayBuffer());
    const magic = String.fromCharCode(head[0], head[1]);
    if (magic !== 'II' && magic !== 'MM') {
      const text = new TextDecoder().decode(head).replace(/\s+/g, ' ').slice(0, 100);
      throw new Error(`not a GeoTIFF (starts with "${text}")`);
    }
    return GeoTIFF.fromBlob(blob);
  }

  // Where the bytes come from:
  //  - layer.data: embedded by the server (it fetched the file with the user's EDL token)
  //  - layer.url:  HTTP Range reads, or one full download if the server ignores Range
  async function openGeoTiff(layer) {
    if (layer.data) return blobToTiff(base64ToBlob(layer.data));
    try {
      const tiff = await GeoTIFF.fromUrl(layer.url);
      await tiff.getImage(0);
      return tiff;
    } catch (err) {
      if (!/full file|byte order/i.test(String((err && err.message) || err))) throw err;
    }
    const resp = await fetch(layer.url);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const declared = Number(resp.headers.get('Content-Length') || 0);
    if (declared > MAX_FULL_DOWNLOAD) {
      throw new Error(`server does not support Range requests and the file is ${(declared / 1048576).toFixed(0)} MB`);
    }
    const blob = await resp.blob();
    if (blob.size > MAX_FULL_DOWNLOAD) throw new Error('server does not support Range requests and the file is too large');
    note(`${layer.title || layer.name}: server ignores Range requests; downloaded the whole file ` +
         `(${(blob.size / 1048576).toFixed(1)} MB).`, 'info');
    return blobToTiff(blob);
  }

  // Decode once with geotiff.js, paint the pixels onto a canvas, and give OpenLayers the
  // canvas as a georeferenced image. (Handing the file to ol.source.GeoTIFF + WebGLTile
  // decoded it a second time and rendered nothing for real Harmony output.)
  async function readGeoTiff(layer) {
    const tiff = await openGeoTiff(layer);
    const image = await tiff.getImage(0);
    // geotiff.js 3.x reads IFD tags lazily via getValue(); 2.x exposed plain properties.
    const tag = (name) =>
      typeof image.fileDirectory.getValue === 'function' ? image.fileDirectory.getValue(name) : image.fileDirectory[name];

    const keys = image.getGeoKeys() || {};
    if (keys.ProjectedCSTypeGeoKey && keys.ProjectedCSTypeGeoKey !== 4326) {
      throw new Error(`file is in EPSG:${keys.ProjectedCSTypeGeoKey}; only lat/lon (EPSG:4326) files are supported`);
    }

    const format = image.getSampleFormat(0); // 1 uint, 2 int, 3 float
    const sentinel = format === 2 ? INT_MIN[image.getBitsPerSample(0)] : undefined;
    const tagNodata = image.getGDALNoData();
    const nodata = layer.nodata ?? (tagNodata === null ? null : tagNodata);

    let scale = layer.scale, offset = layer.offset;
    if (scale === null || offset === null) {
      const meta = (await image.getGDALMetadata(0)) || {}; // async in geotiff.js 3.x
      const pick = (re) => {
        const key = Object.keys(meta).find((k) => re.test(k));
        return key === undefined ? undefined : parseFloat(meta[key]);
      };
      scale = scale ?? pick(/(^|[#_])scale(_factor)?$/i) ?? 1;
      offset = offset ?? pick(/(^|[#_])(add_)?offset$/i) ?? 0;
    }

    const b = image.getBoundingBox();
    const bbox = [Math.min(b[0], b[2]), Math.min(b[1], b[3]), Math.max(b[0], b[2]), Math.max(b[1], b[3])];
    // Most files store the north row first; some store south first.
    const mt = tag('ModelTransformation'), ps = tag('ModelPixelScale');
    const southUp = mt ? mt[5] > 0 : ps ? ps[1] < 0 : false;

    const W = image.getWidth(), H = image.getHeight();
    const k = Math.max(1, W / MAX_RENDER, H / MAX_RENDER);
    const w = Math.max(1, Math.round(W / k)), h = Math.max(1, Math.round(H / k));
    const raster = k > 1
      ? await tiff.readRasters({ samples: [0], width: w, height: h, interleave: true }) // picks an overview if any
      : await image.readRasters({ samples: [0], interleave: true });
    if (k > 1) note(`${layer.title || layer.name}: showing a ${w}×${h} version of the ${W}×${H} raster.`, 'info');

    const valid = (v) => Number.isFinite(v) && v !== nodata && v !== sentinel && Math.abs(v) < 1e30;
    let lo = Infinity, hi = -Infinity;
    for (const v of raster) {
      if (!valid(v)) continue;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
    }
    return { raster, w, h, W, H, bbox, southUp, scale, offset, valid, rawMin: lo, rawMax: hi };
  }

  function lookupTable(colors) {
    return Array.from({ length: 256 }, (_, i) => {
      const t = (i / 255) * (colors.length - 1);
      const j = Math.min(Math.floor(t), colors.length - 2), f = t - j;
      return colors[j].map((c, n) => Math.round(c + (colors[j + 1][n] - c) * f));
    });
  }

  async function addGeoTiff(layer) {
    const label = layer.title || layer.name;
    let info;
    try {
      info = await readGeoTiff(layer);
    } catch (err) {
      return note(`${label}: could not read GeoTIFF (${err.message || err}).` +
                  (layer.data ? '' : ' Check the URL is reachable, sends CORS headers, and is allowed by the host CSP.'),
                  'error');
    }
    const { raster, w, h, bbox, southUp, scale, offset, valid } = info;
    const toPhys = (raw) => raw * scale + offset;
    if (!Number.isFinite(info.rawMin)) note(`${label}: no valid pixels found.`);

    const dataLo = toPhys(Math.min(info.rawMin, info.rawMax)), dataHi = toPhys(Math.max(info.rawMin, info.rawMax));
    const vmin = layer.vmin ?? dataLo;
    let vmax = layer.vmax ?? dataHi;
    if (!(vmax > vmin)) vmax = vmin + 1;

    // Paint: physical value -> 256-step colormap; invalid pixels stay transparent.
    const lut = lookupTable(layer.colors);
    const canvas = document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext('2d');
    const pixels = ctx.createImageData(w, h);
    for (let row = 0; row < h; row++) {
      const src = (southUp ? h - 1 - row : row) * w;
      for (let col = 0; col < w; col++) {
        const v = raster[src + col];
        if (!valid(v)) continue;
        const t = (toPhys(v) - vmin) / (vmax - vmin);
        const c = lut[Math.max(0, Math.min(255, Math.round(t * 255)))];
        const o = (row * w + col) * 4;
        pixels.data[o] = c[0]; pixels.data[o + 1] = c[1]; pixels.data[o + 2] = c[2]; pixels.data[o + 3] = 255;
      }
    }
    ctx.putImageData(pixels, 0, 0);

    // ImageCanvas asks for a canvas covering the lat/lon extent it needs; we draw the painted
    // image into it. No image URL is involved, so host CSPs that block data:/blob: images
    // (as MCP hosts' iframes typically do) don't apply. OpenLayers reprojects to Web Mercator.
    const [bw, bs, be, bn] = bbox;
    const olLayer = new ol.layer.Image({
      opacity: layer.opacity,
      visible: layer.visible,
      source: new ol.source.ImageCanvas({
        projection: 'EPSG:4326',
        ratio: 1,
        canvasFunction: (extent, resolution, pixelRatio, size) => {
          const out = document.createElement('canvas');
          out.width = size[0]; out.height = size[1];
          const octx = out.getContext('2d');
          octx.imageSmoothingEnabled = false;
          const [x0, y0, x1, y1] = extent;
          const sx = size[0] / (x1 - x0), sy = size[1] / (y1 - y0);
          octx.drawImage(canvas, (bw - x0) * sx, (y1 - bn) * sy, (be - bw) * sx, (bn - bs) * sy);
          return out;
        },
      }),
    });
    el.addLayer(olLayer, { name: layer.name });

    const legendEntry = legendRow(layer, olLayer);
    colorBar(legendEntry, layer.colors, vmin, vmax, layer.units);

    if (layer.fit && !spec.bounds) fitGeographic(bbox);

    if (spec.showCoordinates) {
      const [west, south, east, north] = bbox;
      el.addEventListener('terra-map-pointer-move', (e) => {
        if (!olLayer.getVisible()) { readout.hidden = true; return; }
        let [lon, lat] = e.detail.coordinate; // terra reports [lon, lat]
        while (lon < west) lon += 360; // wrapped views / 0..360 files
        while (lon >= east && lon - 360 >= west) lon -= 360;
        const col = Math.floor(((lon - west) / (east - west)) * w);
        const row = Math.floor(((north - lat) / (north - south)) * h);
        const v = col >= 0 && col < w && row >= 0 && row < h ? raster[(southUp ? h - 1 - row : row) * w + col] : NaN;
        if (!valid(v)) { readout.hidden = true; return; }
        readout.hidden = false;
        readout.textContent = `${label}: ${fmt(toPhys(v))}${layer.units ? ' ' + layer.units : ''}`;
      });
    }
  }

  async function addGibs(layer) {
    // Embedded WMS image: decode once into a canvas, draw via ImageCanvas.
    // Using a canvas (not ImageBitmap) in canvasFunction avoids a SecurityError that
    // ctx.drawImage(ImageBitmap) throws in sandboxed iframes on some browsers.
    if (layer.image && layer.imageBbox) {
      const mime = layer.imageFmt === 'jpg' ? 'image/jpeg' : 'image/png';
      let srcCanvas;
      try {
        // createImageBitmap is faster but throws SecurityError in sandboxed Firefox.
        const bytes = Uint8Array.from(atob(layer.image), c => c.charCodeAt(0));
        const bm = await createImageBitmap(new Blob([bytes], { type: mime }));
        srcCanvas = document.createElement('canvas');
        srcCanvas.width = bm.width; srcCanvas.height = bm.height;
        srcCanvas.getContext('2d').drawImage(bm, 0, 0);
        bm.close && bm.close();
      } catch (_) {
        // Fall back to <img> + data URL (works in sandboxed iframes where createImageBitmap is blocked).
        srcCanvas = await new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = () => {
            const c = document.createElement('canvas');
            c.width = img.naturalWidth; c.height = img.naturalHeight;
            c.getContext('2d').drawImage(img, 0, 0);
            resolve(c);
          };
          img.onerror = () => reject(new Error('could not decode embedded GIBS image'));
          img.src = `data:${mime};base64,${layer.image}`;
        });
      }
      const [bw, bs, be, bn] = layer.imageBbox;
      const olLayer = new ol.layer.Image({
        opacity: layer.opacity,
        visible: layer.visible,
        source: new ol.source.ImageCanvas({
          projection: 'EPSG:4326',
          ratio: 1,
          canvasFunction: (extent, _res, _pr, size) => {
            const out = document.createElement('canvas');
            out.width = size[0]; out.height = size[1];
            const ctx = out.getContext('2d');
            const [x0, y0, x1, y1] = extent;
            const sx = size[0] / (x1 - x0), sy = size[1] / (y1 - y0);
            ctx.drawImage(srcCanvas, (bw - x0) * sx, (y1 - bn) * sy, (be - bw) * sx, (bn - bs) * sy);
            return out;
          },
        }),
      });
      el.addLayer(olLayer, { name: layer.name });
      legendRow(layer, olLayer);
      if (!spec.bounds) fitGeographic(layer.imageBbox);
      return;
    }
    // Client-side XYZ tiles (public layers, no embedding needed).
    let errors = 0;
    const source = new ol.source.XYZ({
      url: layer.url,
      maxZoom: layer.maxZoom,
      crossOrigin: 'anonymous',
      attributions: 'NASA EOSDIS GIBS',
      wrapX: true,
    });
    source.on('tileloaderror', () => {
      if (++errors === 3) note(`${layer.title || layer.name}: GIBS tiles failing; check layer id, date and tile matrix set.`);
    });
    const olLayer = new ol.layer.Tile({ source, opacity: layer.opacity, visible: layer.visible });
    el.addLayer(olLayer, { name: layer.name });
    legendRow(layer, olLayer);
  }

  function addFootprints(layer) {
    const features = layer.boxes.map((b) =>
      new ol.Feature(ol.geom.Polygon.fromExtent(ol.proj.transformExtent(unwrap(b), 'EPSG:4326', 'EPSG:3857'))));
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(layer.color.slice(i, i + 2), 16));
    const olLayer = new ol.layer.Vector({
      source: new ol.source.Vector({ features }),
      opacity: layer.opacity,
      visible: layer.visible,
      style: new ol.style.Style({
        fill: new ol.style.Fill({ color: `rgba(${r},${g},${b},0.12)` }),
        stroke: new ol.style.Stroke({ color: layer.color, width: 2 }),
      }),
    });
    el.addLayer(olLayer, { name: layer.name, position: 'top' });
    legendRow(layer, olLayer);
  }

  // ------------------------------------------------------------------ build
  if (spec.bounds) fitGeographic(spec.bounds);

  const builders = { gibs: addGibs, geotiff: addGeoTiff, footprints: addFootprints };
  for (const layer of spec.layers) {
    try {
      await builders[layer.type](layer);
    } catch (err) {
      note(`${layer.title || layer.name}: ${err.message || err}`, 'error');
    }
  }
  document.body.dataset.ready = 'true';
})();
