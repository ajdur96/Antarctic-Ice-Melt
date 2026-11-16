"""DC step 1: flood level (spill elevation) for every 10 m cell, seeded from tidal water and the map edge.
Needs dem10.npy / tr10.json (mosaic of the 3DEP tiles) and the NLCD GeoTIFF in DATA."""
import sys
DATA = sys.argv[1] if len(sys.argv) > 1 else "data"
import numpy as np, json, rasterio, time
from rasterio.warp import reproject, Resampling
from rasterio.transform import Affine
from skimage.morphology import reconstruction
dem = np.load('dem10.npy').astype(np.float32); tr = Affine(*json.load(open('tr10.json')))
H, W = dem.shape
# NLCD -> 10 m UTM grid
nlcd = np.zeros((H, W), np.uint8)
with rasterio.open(DATA + '/dc_nlcd2021.tif') as s:
    reproject(rasterio.band(s, 1), nlcd, dst_transform=tr, dst_crs='EPSG:26918', resampling=Resampling.nearest)
print('nlcd classes', np.unique(nlcd, return_counts=True))
np.save('nlcd10.npy', nlcd)
# seeds: map boundary + tidal open water (NLCD 11 below 3 m)
seed = np.zeros((H, W), bool); seed[0, :] = seed[-1, :] = seed[:, 0] = seed[:, -1] = True
seed |= (nlcd == 11) & (dem < 3)
t = time.time()
marker = np.where(seed, dem, dem.max() + 1)
fill = reconstruction(marker, dem, method='erosion').astype(np.float32)   # spill level: min water level that reaches each cell
print('reconstruction s', round(time.time() - t, 1), 'cells raised', (fill > dem + 0.01).mean())
np.save('fill10.npy', fill)
