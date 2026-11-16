"""DC step 2: crop to the display extent and build web data: shaded land-cover base (10 m + 20 m lite),
20 m flood grid, land-cover and building flood tables, packed buildings, TIGER state and Arlington boundaries.
Usage: python 2_pack_web_data.py <data folder> <tiger geojson folder>  (writes site2/dc/)"""
import sys
DATA = sys.argv[1] if len(sys.argv) > 1 else "data"
TIGER = sys.argv[2] if len(sys.argv) > 2 else "tiger"
import numpy as np, json, struct, gzip, os, base64
from PIL import Image
from shapely.geometry import shape, box
from shapely.ops import transform
from pyproj import Transformer
R0, R1, C0, C1 = 804, 3776, 1096, 5116          # crop of the 10 m grid (even numbers for 2x2 blocks)
dem = np.load('dem10.npy')[R0:R1, C0:C1]; fill = np.load('fill10.npy')[R0:R1, C0:C1]; nlcd = np.load('nlcd10.npy')[R0:R1, C0:C1]
tr0 = json.load(open('tr10.json')); X0 = tr0[2] + C0 * 10; Y0top = tr0[5] - R0 * 10
H, W = dem.shape; print('crop', W, H, X0, Y0top)
old = json.load(open('dc_meta.json'))
nlcdPal = {int(k): v for k, v in old['nlcdPal'].items()}
water = nlcd == 11
# --- base images (full 10 m and lite 20 m)
lut = np.zeros((256, 3), np.float32)
for k, v in nlcdPal.items(): lut[k] = v
paper = np.array([238, 234, 226], np.float32); soft = lut * 0.6 + paper * 0.4; soft[11] = (120, 165, 200)
rgb = soft[nlcd]
gy, gx = np.gradient(dem.astype(np.float32), 10); gx *= 3; gy *= 3
az, alt = np.radians(315), np.radians(45)
slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
hs = np.clip((np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - aspect)) / np.sin(alt), 0.5, 1.2)
rgb = np.where(water[..., None], rgb, rgb * hs[..., None])
img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8))
os.makedirs('site2/dc', exist_ok=True)
img.save('site2/dc/dc_base.webp', quality=72, method=6)
img.resize((W // 2, H // 2), Image.LANCZOS).save('site2/dc/dc_base_lite.webp', quality=75, method=6)
# --- 20 m flood grid
blk = lambda a: a.reshape(H // 2, 2, W // 2, 2)
f20 = blk(fill).min((1, 3)); w20 = blk(water).any((1, 3))
fl = np.clip(np.ceil(f20 / 0.5), 0, 254).astype(np.uint8); fl[f20 > 127] = 255; fl[w20] = 0
open('site2/dc/dc_flood.txt', 'w').write(base64.b64encode(gzip.compress(fl.tobytes(), 9)).decode())
# --- land-cover tables
levels = np.arange(0, 80.01, 0.5); classes = [21, 22, 23, 24, 31, 41, 42, 43, 52, 71, 81, 82, 90, 95]
fv = fill[~water]; nv = nlcd[~water]; area = {}
for c in classes:
    vals = np.sort(fv[nv == c]); area[c] = (np.searchsorted(vals, levels, side='right') * 100 / 1e6).round(3).tolist()
# --- buildings (same packing as before, only those inside the crop)
b = open(DATA + '/dc_buildings.bin', 'rb').read()
hl = struct.unpack('<I', b[:4])[0]; hdr = json.loads(b[4:4 + hl]); o = 4 + hl; OX, OY = hdr['origin']
def sample(a, xs, ys):
    c = np.clip(((xs - X0) / 10).astype(int), 0, W - 1); r = np.clip(((Y0top - ys) / 10).astype(int), 0, H - 1); return a[r, c]
recs, startL, subL, occs = [], [], [], []
while o < len(b):
    h, e, c, nvx = struct.unpack_from('<ffBH', b, o); o += 11
    x0, y0 = struct.unpack_from('<ii', b, o); o += 8
    d = np.frombuffer(b, '<i2', (nvx - 1) * 2, o).reshape(-1, 2); o += (nvx - 1) * 4
    xs = np.concatenate([[x0], x0 + np.cumsum(d[:, 0])]) / 10 + OX; ys = np.concatenate([[y0], y0 + np.cumsum(d[:, 1])]) / 10 + OY
    cx, cy = xs.mean(), ys.mean()
    if not (X0 < cx < X0 + W * 10 and Y0top - H * 10 < cy < Y0top): continue
    px = np.append(xs, cx); py = np.append(ys, cy)
    fs = float(sample(fill, px, py).min()); top = float(sample(dem, px, py).max()) + (h if h > 0 else 6.0)
    recs.append((xs, ys)); startL.append(fs); subL.append(max(fs, top)); occs.append(c)
startL = np.array(startL); subL = np.array(subL); occs = np.array(occs); print('buildings', len(recs))
bstats = {'start': np.searchsorted(np.sort(startL), levels, side='right').tolist(), 'sub': np.searchsorted(np.sort(subL), levels, side='right').tolist()}
occNames = {v: k for k, v in hdr['occ'].items()}
bocc = {occNames[k]: {'start': np.searchsorted(np.sort(startL[occs == k]), levels, side='right').tolist(),
                      'sub': np.searchsorted(np.sort(subL[occs == k]), levels, side='right').tolist()} for k in sorted(set(occs.tolist()))}
TW = 1000; ntx, nty = int(np.ceil(W * 10 / TW)), int(np.ceil(H * 10 / TW))
tx = np.array([int((r[0].mean() - X0) // TW) for r in recs]); ty = np.array([int((Y0top - r[1].mean()) // TW) for r in recs])
tileId = np.clip(ty, 0, nty - 1) * ntx + np.clip(tx, 0, ntx - 1); order = np.argsort(tileId, kind='stable')
qz = lambda v: min(255, max(0, int(np.ceil(v / 0.5))))
out = bytearray(); counts = np.zeros(ntx * nty, int)
for i in order:
    xs, ys = recs[i]
    ux = np.round((xs - X0) * 2).astype(np.int64); uy = np.round((Y0top - ys) * 2).astype(np.int64)
    dx, dy = np.diff(ux), np.diff(uy)
    if len(ux) > 65535 or np.abs(dx).max(initial=0) > 32767 or np.abs(dy).max(initial=0) > 32767: continue
    out += struct.pack('<BBBHii', qz(startL[i]), qz(subL[i]), int(occs[i]), len(ux), int(ux[0]), int(uy[0]))
    out += np.stack([dx, dy], 1).astype('<i2').tobytes(); counts[tileId[i]] += 1
open('site2/dc/dc_buildings.txt', 'w').write(base64.b64encode(gzip.compress(bytes(out), 9)).decode())
# --- boundaries
tr = Transformer.from_crs(4326, 26918, always_xy=True)
ext = box(X0, Y0top - H * 10, X0 + W * 10, Y0top)
toPx = lambda l: [[round((x - X0) / 10, 1), round((Y0top - y) / 10, 1)] for x, y in l.coords]
g = json.load(open(TIGER + '/state.geo.json')); lines = []
for f in g['features']:
    if str(f['properties'].get('STATEFP10', '')).zfill(2) not in ('11', '24', '51'): continue
    bb = transform(tr.transform, shape(f['geometry'])).boundary.intersection(ext.buffer(-1)).simplify(4)
    lines += [toPx(l) for l in getattr(bb, 'geoms', [bb]) if not l.is_empty and l.length >= 50]
labels = []
for name, lon, lat in [('VIRGINIA', -77.27, 38.82), ('MARYLAND', -77.15, 39.012), ('MARYLAND', -76.95, 38.80), ('D.C.', -77.015, 38.905)]:
    x, y = tr.transform(lon, lat); labels.append([name, round((x - X0) / 10), round((Y0top - y) / 10)])
cg = json.loads(open(TIGER + '/county.geo.json', encoding='latin-1').read())
arl = transform(tr.transform, shape([f for f in cg['features'] if str(f['properties'].get('GEOID10')) == '51013'][0]['geometry']))
ab = arl.boundary.simplify(3)
counties = {'lines': [toPx(l) for l in getattr(ab, 'geoms', [ab])], 'labels': [['ARLINGTON', round((arl.centroid.x - X0) / 10), round((Y0top - arl.centroid.y) / 10)]]}
meta = dict(W=W // 2, H=H // 2, cell=20, baseW=W, baseH=H, x0=X0, y0=Y0top, crs='EPSG:26918', levels=[0, 80, 0.5], areaKm2=area,
            nlcdNames=old['nlcdNames'], nlcdPal=old['nlcdPal'], bldTotal=int(counts.sum()), bld=bstats, bldOcc=bocc, occNames=occNames,
            tiles=dict(size=TW, nx=ntx, ny=nty, counts=counts.tolist()), states={'lines': lines, 'labels': labels}, counties=counties)
json.dump(meta, open('site2/dc/dc_meta.json', 'w'))
for f in sorted(os.listdir('site2/dc')): print(f, round(os.path.getsize('site2/dc/' + f) / 1e6, 2), 'MB')
