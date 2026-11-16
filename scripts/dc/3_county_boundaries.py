"""DC step 3: county and independent-city boundaries (Census TIGER 2010) and labels for dc_meta.json.
Usage: python 3_county_boundaries.py <dc_meta.json> <county.geo.json>"""
import json, sys, warnings; warnings.filterwarnings('ignore')
from shapely.geometry import shape, box
from shapely.ops import transform, unary_union
from pyproj import Transformer
metaPath, countyGeo = sys.argv[1], sys.argv[2]
m = json.load(open(metaPath)); X0, Y0, BW, BH = m['x0'], m['y0'], m['baseW'], m['baseH']
tr = Transformer.from_crs(4326, 26918, always_xy=True)
ext = box(X0, Y0 - BH * 10, X0 + BW * 10, Y0)
toPx = lambda l: [[round((x - X0) / 10, 1), round((Y0 - y) / 10, 1)] for x, y in l.coords]
px = lambda x, y: [round((x - X0) / 10), round((Y0 - y) / 10)]
# label text, size class (1 = county, 2 = small city), optional fixed lon/lat
names = {'51013': ('ARLINGTON', 1, None), '51510': ('ALEXANDRIA', 2, None), '51610': ('FALLS CHURCH', 2, None),
         '51600': ('FAIRFAX', 2, None), '51059': ('FAIRFAX COUNTY', 1, (-77.24, 38.86)),
         '24031': ('MONTGOMERY COUNTY', 1, (-77.12, 39.00)), '24033': ("PRINCE GEORGE'S", 1, (-76.925, 38.83))}
cg = json.loads(open(countyGeo, encoding='latin-1').read())
lines, labels = [], []
for f in cg['features']:
    gid = str(f['properties']['GEOID10'])
    if gid not in names: continue
    g = transform(tr.transform, shape(f['geometry']))
    b = g.boundary.intersection(ext.buffer(-1)).simplify(3)
    lines += [toPx(l) for l in getattr(b, 'geoms', [b]) if not l.is_empty and l.length >= 30]
    text, size, ll = names[gid]
    if ll: x, y = tr.transform(*ll)
    else: c = g.intersection(ext); pt = c.centroid if c.contains(c.centroid) else c.representative_point(); x, y = pt.x, pt.y
    labels.append([text, *px(x, y), size])
m['counties'] = {'lines': lines, 'labels': labels}
json.dump(m, open(metaPath, 'w')); print(len(lines), 'lines;', labels)
