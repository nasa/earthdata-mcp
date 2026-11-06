(async()=>{
// @PARAMS@
  const _ext4326 = _P.bbox;
  const _ext = ol.proj.transformExtent(_ext4326, 'EPSG:4326', 'EPSG:3857');
  const _p = new URLSearchParams({
    SERVICE: 'WMS', VERSION: '1.3.0', REQUEST: 'GetMap',
    CRS: 'EPSG:3857', BBOX: _ext.join(','),
    WIDTH: _P.img_size, HEIGHT: _P.img_size,
    ..._P.params
  });
  // fetch()→blob avoids canvas-taint and img.crossOrigin CORS failures.
  const _blob = await fetch(_P.url + '?' + _p.toString()).then(r => r.blob());
  const _burl = URL.createObjectURL(_blob);
  const _img = new Image();
  await new Promise((r, x) => { _img.onload = r; _img.onerror = x; _img.src = _burl; });
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
  });
})()
