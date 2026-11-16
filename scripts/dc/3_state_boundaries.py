"""DC step 3: add Census TIGER 2010 state boundaries (DC, MD, VA) and labels to dc_meta.json.
Usage: python 3_state_boundaries.py <state.geo.json> <dc_meta.json>"""
import json, sys
from shapely.geometry import shape, box
from shapely.ops import transform
from pyproj import Transformer
g = json.load(open(sys.argv[1])); metaPath = sys.argv[2]; m = json.load(open(metaPath))
X0, Y0 = m['x0'], m['y0']; BW, BH = m['baseW'], m['baseH']
tr = Transformer.from_crs(4326, 26918, always_xy=True)
ext = box(X0, Y0 - BH * 10, X0 + BW * 10, Y0)
lines = []
for f in g['features']:
    if str(f['properties'].get('STATEFP10', '')).zfill(2) not in ('11', '24', '51'): continue
    b = transform(tr.transform, shape(f['geometry'])).boundary.intersection(ext.buffer(-1)).simplify(4)
    for l in getattr(b, 'geoms', [b]):
        if not l.is_empty and l.length >= 50:
            lines.append([[round((x - X0) / 10, 1), round((Y0 - y) / 10, 1)] for x, y in l.coords])
labels = []
for name, lon, lat in [('VIRGINIA', -77.30, 38.80), ('MARYLAND', -77.10, 39.06), ('MARYLAND', -76.86, 38.80), ('D.C.', -77.015, 38.905)]:
    x, y = tr.transform(lon, lat); labels.append([name, round((x - X0) / 10), round((Y0 - y) / 10)])
m['states'] = {'lines': lines, 'labels': labels}
json.dump(m, open(metaPath, 'w'))
