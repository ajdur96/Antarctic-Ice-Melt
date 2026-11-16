"""Step 3: per-cell thaw order (elevation, distance from pole, marine bed, smooth noise).
Usage: python 3_thaw_order.py  (updates data.json)"""
import numpy as np, json, gzip, base64
from scipy.ndimage import gaussian_filter
d = json.load(open('data.json')); n = d['n']
dec = lambda s, t: np.frombuffer(gzip.decompress(base64.b64decode(s)), t).reshape(n, n)
bed = dec(d['bed'], '<i2').astype(float); H = dec(d['thk'], '<u2').astype(float); cls = dec(d['cls'], 'u1')
ice = (cls == 1) | (cls == 2)
rhoW, rhoI = 1027, 917
surf = np.where(cls == 2, H * (1 - rhoI / rhoW), bed + H)
x = d['x0'] + np.arange(n) * 5000; y = d['y0'] - np.arange(n) * 5000
X, Y = np.meshgrid(x, y); rho = np.hypot(X, Y)
elevTerm = np.clip(surf / 3800, 0, 1)                 # high = late
poleTerm = 1 - np.clip(rho / 2400e3, 0, 1)            # near pole = late
marineTerm = (bed > 0).astype(float)                  # land-based = late
rng = np.random.default_rng(7)
noise = sum(gaussian_filter(rng.standard_normal((n, n)), s) * w for s, w in [(40, 1.0), (15, 0.4)])
noise = (noise - noise[ice].mean()) / noise[ice].std()
v = 0.45 * elevTerm + 0.3 * poleTerm + 0.15 * marineTerm + 0.08 * noise
v = gaussian_filter(np.where(ice, v, np.nan_to_num(v)), 4)
v[cls == 2] = v[cls == 2] * 0.5 - 0.15                # shelves go early
# rank-normalise over ice cells -> uniform 0..1
vals = v[ice]; ranks = vals.argsort().argsort() / (len(vals) - 1)
out = np.zeros((n, n), np.uint8); out[ice] = np.round(ranks * 255).astype(np.uint8)
d['ord'] = base64.b64encode(gzip.compress(out.tobytes(), 9)).decode()
json.dump(d, open('data.json', 'w'))
# check SLE at 5 km
area = (5000**2)
vaf = lambda h: np.where(cls == 1, np.maximum(0, h - np.maximum(0, -bed) * rhoW / rhoI), 0)
print('SLE 5km approx (no scale corr):', (vaf(H).sum() * area) * rhoI / rhoW / 3.618e14, len(d['ord']))
