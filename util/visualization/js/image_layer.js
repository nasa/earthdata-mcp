(async()=>{
// @PARAMS@
  const _src = _P.url;
  const _img = new Image();
  // data: URIs are same-origin — load directly, no fetch needed.
  // fetch('data:...') is blocked in sandboxed iframes (e.g. MCP Jam).
  // External URLs use fetch()→blob to avoid cross-origin canvas taint.
  if (_src.startsWith('data:')) {
    await new Promise((r, x) => { _img.onload = r; _img.onerror = x; _img.src = _src; });
  } else {
    const _blob = await fetch(_src).then(r => r.blob());
    const _burl = URL.createObjectURL(_blob);
    await new Promise((r, x) => { _img.onload = r; _img.onerror = x; _img.src = _burl; });
  }
  const _ext = ol.proj.transformExtent(_P.extent, 'EPSG:4326', 'EPSG:3857');
  return new ol.layer.Image({
    extent: _ext,
    opacity: _P.opacity,
    source: new ol.source.ImageCanvas({
      canvasFunction: (_e, _r, pr, sz) => {
        const c = document.createElement('canvas');
        c.width = Math.round(sz[0] * pr);
        c.height = Math.round(sz[1] * pr);
        c.getContext('2d').drawImage(_img, 0, 0, c.width, c.height);
        return c;
      },
      projection: 'EPSG:3857'
    })
  })
})()
