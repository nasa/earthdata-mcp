(()=>{
// @PARAMS@
  return new ol.layer.Vector({
    source: new ol.source.Vector({
      features: _P.coords.map(c =>
        new ol.Feature({ geometry: new ol.geom.Point(ol.proj.fromLonLat(c)) })
      )
    }),
    style: new ol.style.Style({
      image: new ol.style.Circle({
        radius: _P.radius,
        fill: new ol.style.Fill({ color: _P.color }),
        stroke: new ol.style.Stroke({ color: _P.stroke_color, width: _P.stroke_width })
      })
    })
  })
})()
