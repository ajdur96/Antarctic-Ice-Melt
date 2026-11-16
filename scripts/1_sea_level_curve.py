"""Step 1: sea-level-rise curve for even thinning, from full 1 km Bedmap2 grids.
Usage: python 1_sea_level_curve.py <bedmap2_bin folder>  -> slr.npy"""
import numpy as np, sys, json, gzip, base64
src = sys.argv[1]
N = 6667
bed = np.fromfile(f'{src}/bedmap2_bed.flt', dtype='<f4').reshape(N, N)
thk = np.fromfile(f'{src}/bedmap2_thickness.flt', dtype='<f4').reshape(N, N)
msk = np.fromfile(f'{src}/bedmap2_icemask_grounded_and_shelves.flt', dtype='<f4').reshape(N, N)

rhoI, rhoW, oceanArea = 917.0, 1027.0, 3.618e14
# coords (row 0 = top = y max for ESRI float grids)
xs = -3333000 + np.arange(N) * 1000.0
ys = 3333000 - np.arange(N) * 1000.0
X, Y = np.meshgrid(xs, ys)
rho = np.hypot(X, Y)
# spherical approx of polar-stereo scale factor, true scale at 71S
phi_c = np.radians(71)
R = 6371000.0
t = rho / (R * (1 + np.sin(phi_c)))
colat = 2 * np.arctan(t)
lat = np.pi / 2 - colat
k = (1 + np.sin(phi_c)) / (1 + np.sin(lat))
trueArea = 1e6 / k**2

grounded = (msk == 0)
H = np.where(thk > 0, thk, 0)
b = np.where(bed == -9999, -4000, bed)

def vaf(Hc):
    return np.where(grounded, np.maximum(0, Hc - np.maximum(0, -b) * rhoW / rhoI), 0)
V0 = (vaf(H) * trueArea).sum()
fs = np.linspace(0, 1, 101)
slr = []
for f in fs:
    V = (vaf(H * (1 - f)) * trueArea).sum()
    slr.append((V0 - V) * rhoI / rhoW / oceanArea)
print('full SLE (VAF only):', slr[-1])
np.save('slr.npy', np.array(slr))
print('grounded ice vol km3', (H*grounded*trueArea).sum()/1e9)
