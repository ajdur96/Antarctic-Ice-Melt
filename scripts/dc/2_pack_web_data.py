"""DC step 2: shaded land-cover base image, 20 m flood grid, stats tables and packed buildings.
Outputs go to ../../dc after base64-encoding the .bin.gz files (see 3_build_html.py)."""
import sys
DATA = sys.argv[1] if len(sys.argv) > 1 else "data"
import numpy as np, json, struct, gzip
from PIL import Image
dem = np.load('dem10.npy'); fill = np.load('fill10.npy'); nlcd = np.load('nlcd10.npy')
tr = json.load(open('tr10.json')); X0, Y0top = tr[2], tr[5]
dem = dem[:4580, :6176]; fill = fill[:4580, :6176]; nlcd = nlcd[:4580, :6176]
H, W = dem.shape
nlcdPal = {11:(84,131,180),21:(222,206,190),22:(214,170,150),23:(200,120,110),24:(160,70,70),31:(190,180,170),
 41:(118,170,105),42:(60,120,80),43:(150,185,120),52:(205,190,140),71:(225,220,165),81:(220,215,120),82:(190,150,80),
 90:(150,190,190),95:(120,170,190),0:(200,200,200)}
lut = np.zeros((256,3),np.uint8)
for k,v in nlcdPal.items(): lut[k]=v
rgb = lut[nlcd].astype(np.float32)
# hillshade (NW sun, 3x exaggeration)
gy, gx = np.gradient(dem.astype(np.float32), 10)
gx*=3; gy*=3
az, alt = np.radians(315), np.radians(45)
slope = np.arctan(np.hypot(gx, gy)); aspect = np.arctan2(-gx, gy)
hs = np.sin(alt)*np.cos(slope) + np.cos(alt)*np.sin(slope)*np.cos(az - aspect)
hs = np.clip(hs / np.sin(alt), 0.45, 1.25)
# gentle elevation tint: lift high ground slightly
tint = np.clip(dem / 160, 0, 1)[..., None]
rgb = rgb * (0.92 + 0.12 * tint)
water = (nlcd == 11)
rgb = np.where(water[..., None], rgb, rgb * hs[..., None])
Image.fromarray(np.clip(rgb,0,255).astype(np.uint8)).save('dc_base.jpg', quality=84, optimize=True, progressive=True)
# 20 m flood grid: flood level = min of 2x2 (any part wet), elev = mean
q = lambda a: np.clip(np.ceil(a / 0.5), 0, 254).astype(np.uint8)
blk = lambda a: a.reshape(H//2, 2, W//2, 2)
f20 = blk(fill).min((1,3)); e20 = blk(dem).mean((1,3))
w20 = blk(water).any((1,3))
fl = q(f20); fl[f20 > 127] = 255; fl[w20] = 0   # existing water handled by base map
el = np.clip(np.round(np.maximum(e20, 0) / 0.5), 0, 255).astype(np.uint8)
open('dc_flood.bin.gz','wb').write(gzip.compress(fl.tobytes() + el.tobytes(), 9))
# area tables by NLCD class, 0.5 m levels to 80 m
levels = np.arange(0, 80.01, 0.5)
classes = [21,22,23,24,31,41,42,43,52,71,81,82,90,95]
fv = fill[~water]; nv = nlcd[~water]
area = {}
for c in classes:
    vals = np.sort(fv[nv == c]); area[c] = (np.searchsorted(vals, levels, side='right') * 100 / 1e6).round(3).tolist()  # km2
# buildings
b = open(DATA + '/dc_buildings.bin','rb').read()
hl = struct.unpack('<I', b[:4])[0]; hdr = json.loads(b[4:4+hl]); o = 4 + hl
OX, OY = hdr['origin']
recs = []; startL = []; subL = []; occs = []
def sample(a, xs, ys):
    c = np.clip(((xs - X0) / 10).astype(int), 0, W-1); r = np.clip(((Y0top - ys) / 10).astype(int), 0, H-1); return a[r, c]
while o < len(b):
    h, e, c, nvx = struct.unpack_from('<ffBH', b, o); o += 11
    x0, y0 = struct.unpack_from('<ii', b, o); o += 8
    d = np.frombuffer(b, '<i2', (nvx-1)*2, o).reshape(-1, 2); o += (nvx-1)*4
    xs = np.concatenate([[x0], x0 + np.cumsum(d[:,0])]) / 10 + OX
    ys = np.concatenate([[y0], y0 + np.cumsum(d[:,1])]) / 10 + OY
    px = np.append(xs, xs.mean()); py = np.append(ys, ys.mean())
    if not ((px > X0) & (px < X0 + W*10) & (py < Y0top) & (py > Y0top - H*10)).any(): continue
    fs = float(sample(fill, px, py).min()); top = float(sample(dem, px, py).max()) + (h if h > 0 else 6.0)
    sub = max(fs, top)
    recs.append((xs, ys)); startL.append(fs); subL.append(sub); occs.append(c)
startL = np.array(startL); subL = np.array(subL); occs = np.array(occs)
print('buildings', len(recs))
bstats = {'start': (np.searchsorted(np.sort(startL), levels, side='right')).tolist(),
          'sub': (np.searchsorted(np.sort(subL), levels, side='right')).tolist()}
occNames = {v:k for k,v in hdr['occ'].items()}
bocc = {}
for k in sorted(set(occs.tolist())):
    bocc[occNames[k]] = {'start': np.searchsorted(np.sort(startL[occs==k]), levels, side='right').tolist(),
                         'sub': np.searchsorted(np.sort(subL[occs==k]), levels, side='right').tolist()}
# spatial sort into 1 km tiles; coords in 0.5 m units relative to grid origin
TW = 1000
tx = np.array([int((r[0].mean() - X0) // TW) for r in recs]); ty = np.array([int((Y0top - r[1].mean()) // TW) for r in recs])
ntx, nty = int(np.ceil(W*10/TW)), int(np.ceil(H*10/TW))
order = np.lexsort((tx, ty)); tileId = np.clip(ty, 0, nty-1) * ntx + np.clip(tx, 0, ntx-1)
order = np.argsort(tileId, kind='stable')
out = bytearray(); tileStart = np.zeros(ntx*nty + 1, np.int64); offsets = []
counts = np.bincount(tileId, minlength=ntx*nty)
qz = lambda v: min(255, max(0, int(np.ceil(v / 0.5))))
for i in order:
    xs, ys = recs[i]
    ux = np.round((xs - X0) * 2).astype(np.int64); uy = np.round((Y0top - ys) * 2).astype(np.int64)
    dx = np.diff(ux); dy = np.diff(uy)
    if len(ux) > 65535 or np.abs(dx).max(initial=0) > 32767 or np.abs(dy).max(initial=0) > 32767: continue
    out += struct.pack('<BBBHII', qz(startL[i]), qz(subL[i]), int(occs[i]), len(ux), int(ux[0]), int(uy[0]))
    out += np.stack([dx, dy], 1).astype('<i2').tobytes()
tileCounts = counts.tolist()
open('dc_buildings.bin.gz','wb').write(gzip.compress(bytes(out), 9))
meta = dict(W=W//2, H=H//2, cell=20, baseW=W, baseH=H, x0=X0, y0=Y0top, crs='EPSG:26918', levels=[0, 80, 0.5],
            areaKm2=area, nlcdNames={11:'Open water',21:'Developed, open space',22:'Developed, low intensity',23:'Developed, medium intensity',24:'Developed, high intensity',31:'Barren',41:'Deciduous forest',42:'Evergreen forest',43:'Mixed forest',52:'Shrub',71:'Grassland',81:'Pasture',82:'Cultivated crops',90:'Woody wetlands',95:'Herbaceous wetlands'},
            nlcdPal={k:list(v) for k,v in nlcdPal.items()}, bldTotal=int(len(recs)), bld=bstats, bldOcc=bocc, occNames=occNames,
            tiles=dict(size=TW, nx=ntx, ny=nty, counts=tileCounts))
json.dump(meta, open('dc_meta.json','w'))
import os
for f in ['dc_base.jpg','dc_flood.bin.gz','dc_buildings.bin.gz','dc_meta.json']: print(f, round(os.path.getsize(f)/1e6,2),'MB')
for L in (5,10,20,40,57,71): i=int(L/0.5); print(L,'m: bld start',bstats['start'][i],'sub',bstats['sub'][i],'dev km2',sum(area[c][i] for c in (21,22,23,24)))
