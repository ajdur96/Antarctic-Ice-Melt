"""Step 2: resample Bedmap2 to 5 km, classify cells, pack for the web page.
Usage: python 2_downsample.py <bedmap2_bin folder>  -> data.json"""
import numpy as np, sys, gzip, base64, json
src = sys.argv[1]; N = 6667; S = 5  # 5 km
bed = np.fromfile(f'{src}/bedmap2_bed.flt', dtype='<f4').reshape(N, N)
thk = np.fromfile(f'{src}/bedmap2_thickness.flt', dtype='<f4').reshape(N, N)
msk = np.fromfile(f'{src}/bedmap2_icemask_grounded_and_shelves.flt', dtype='<f4').reshape(N, N)
# crop to +-3000 km  (index of x=-3000000: (−3000000+3333000)/1000 = 333)
i0 = 333; n = 6000
sl = (slice(i0, i0+n), slice(i0, i0+n))
bed, thk, msk = bed[sl], thk[sl], msk[sl]
def blk(a): return a.reshape(n//S, S, n//S, S)
bedValid = bed != -9999
bedF = np.where(bedValid, bed, 0)
cnt = blk(bedValid).sum((1,3))
bedD = np.where(cnt > 0, blk(bedF).sum((1,3)) / np.maximum(cnt,1), -4500)
H = np.where(thk > 0, thk, 0)
land = msk != -9999
cls_grounded = blk((msk == 0) & (H > 0)).sum((1,3))
cls_shelf = blk(msk == 1).sum((1,3))
cls_rock = blk(land & (H == 0)).sum((1,3))
cls_ocean = blk(~land).sum((1,3))
stack = np.stack([cls_ocean, cls_grounded, cls_shelf, cls_rock])
cls = stack.argmax(0).astype(np.uint8)
Hd = blk(H).mean((1,3))
Hland = blk(np.where(land, H, 0)).sum((1,3)) / np.maximum(blk(land).sum((1,3)), 1)
Hd = np.where(cls == 0, 0, np.where(cls == 3, 0, Hland))
# rock surface = bed (stored bed already); make sure rock bed > 0 not violated
m = n // S
print('grid', m, 'classes', np.bincount(cls.ravel()))
bedI = np.clip(np.round(bedD), -9000, 9000).astype('<i2')
thkI = np.clip(np.round(Hd), 0, 6000).astype('<u2')
def enc(a): return base64.b64encode(gzip.compress(a.tobytes(), 9)).decode()
slr = np.load('slr.npy')
out = dict(n=m, cell=5000, x0=-3000000+2500, y0=3000000-2500,
           bed=enc(bedI), thk=enc(thkI), cls=enc(cls), slr=[round(float(v),3) for v in slr])
json.dump(out, open('data.json','w'))
print({k: len(v) if isinstance(v,str) else v for k,v in out.items() if k!='slr'})
