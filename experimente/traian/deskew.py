import sys, glob, numpy as np
from PIL import Image
def shear(im, k):
    return im.transform(im.size, Image.AFFINE, (1, k, 0, 0, 1, 0), resample=Image.BICUBIC, fillcolor=255)
for f in sorted(glob.glob(sys.argv[1] + "/r-*.png")):
    im = Image.open(f).convert("L")
    sm = im.resize((im.width // 4, im.height // 4))
    t = max(np.arange(-1.5, 1.51, 0.05), key=lambda t: np.var((np.array(sm.rotate(t, fillcolor=255)) < 160).sum(1)))
    im = im.rotate(t, resample=Image.BICUBIC, fillcolor=255)
    sm = im.resize((im.width // 4, im.height // 4))
    k = max(np.arange(-0.03, 0.0301, 0.001), key=lambda k: np.var((np.array(shear(sm, k)) < 160).sum(0)))
    shear(im, k).save(f.replace("r-", "d-"))
    print(f[-6:-4], round(t, 2), round(k, 3), end="; ")
