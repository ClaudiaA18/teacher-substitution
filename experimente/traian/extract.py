import sys, glob, json, re, subprocess, numpy as np
from PIL import Image

def runs(mask, minlen):
    idx = np.where(mask)[0]
    if len(idx) == 0: return []
    out, cur = [], [idx[0]]
    for i in idx[1:]:
        if i - cur[-1] <= 4: cur.append(i)
        else: out.append(int(np.mean(cur))); cur = [i]
    out.append(int(np.mean(cur)))
    return out

def ocr(img, psm=6):
    r = subprocess.run(["tesseract", "-", "-", "--psm", str(psm), "-l", "eng"], input=img_bytes(img), capture_output=True)
    return r.stdout.decode().strip()

def img_bytes(img):
    import io
    b = io.BytesIO(); img.save(b, "PNG"); return b.getvalue()

def page(path):
    im = Image.open(path).convert("L")
    a = np.array(im) < 140
    a2 = np.array(im) < 210
    H, W = a.shape
    colsum = a.sum(0)
    left = [x for x in runs(colsum > 0.5 * H * 0.8, 1)]
    # name column right edge: strong vertical line between 300 and 450
    cand = [x for x in runs(colsum > 0.6 * colsum.max(), 1)]
    xname = min([x for x in cand if 300 < x < 460], default=379)
    xs = [xname]
    while xs[-1] + 150 < W:
        w = a[:, xs[-1] + 160: xs[-1] + 210].sum(0)
        nx = xs[-1] + 160 + int(np.argmax(w))
        if w.max() < 0.3 * H * 0.8: break
        xs.append(nx)
    strip = a[:, 60:xname - 20].sum(1)
    ys = runs(strip > 0.85 * (xname - 80), 1)
    return im, a, a2, xs, ys

def boundary_v(a, x, y0, y1):
    return max(a[y0 + 12:y1 - 12, x + d - 3:x + d + 4].any(1).mean() for d in range(-18, 19, 3)) > 0.6

def boundary_h(a, y, x0, x1):
    return max(a[y + d - 3:y + d + 4, x0 + 12:x1 - 12].any(0).mean() for d in range(-18, 19, 3)) > 0.6

def extract(path):
    im, a, a2, xs, ys = page(path)
    ys = [y for y in ys if y > 300]
    pitch = min(b - a_ for a_, b in zip(ys, ys[1:]) if b - a_ > 120)
    fixed = [ys[0]]
    for y in ys[1:]:
        n = round((y - fixed[-1]) / pitch)
        for j in range(1, n):
            fixed.append(fixed[-1] + (y - fixed[-1]) // (n - j + 1))
        if n >= 1: fixed.append(y)
    ys = fixed
    rows = list(zip(ys[:-1], ys[1:]))
    cols = list(zip(xs[:-1], xs[1:]))
    nr, nc = len(rows), len(cols)
    par = {(r, c): (r, c) for r in range(nr) for c in range(nc)}
    def f(k):
        while par[k] != k: par[k] = par[par[k]]; k = par[k]
        return k
    for r in range(nr):
        for c in range(nc - 1):
            if not boundary_v(a2, cols[c][1], *rows[r]): par[f((r, c + 1))] = f((r, c))
    for r in range(nr - 1):
        for c in range(nc):
            if not boundary_h(a2, rows[r][1], *cols[c]): par[f((r + 1, c))] = f((r, c))
    groups = {}
    for k in par: groups.setdefault(f(k), []).append(k)
    names = []
    for y0, y1 in rows:
        names.append(" ".join(ocr(im.crop((50, y0 + 5, xs[0] - 5, y1 - 5)).resize(((xs[0] - 55) * 1, (y1 - y0 - 10)))).split()))
    cells = []
    for g in groups.values():
        rr = sorted({k[0] for k in g}); cc = sorted({k[1] for k in g})
        x0, x1 = cols[cc[0]][0] + 6, cols[cc[-1]][1] - 6
        y0, y1 = rows[rr[0]][0] + 6, rows[rr[-1]][1] - 6
        if a[y0 + 20:y1 - 20, x0 + 20:x1 - 20].sum() < 150: continue
        c = im.crop((x0, y0, x1, y1))
        h = c.height
        top = c.crop((0, 0, c.width, int(h * 0.62)))
        bot = c.crop((0, int(h * 0.55), c.width, h)) if len(cc) == 1 and len(rr) == 1 else c.crop((0, int(h * 0.45), c.width, h))
        cls = ocr(top.resize((top.width * 2, top.height * 2), Image.LANCZOS), 6)
        bb = bot.resize((bot.width * 4, bot.height * 4), Image.LANCZOS).point(lambda v: 0 if v < 170 else 255)
        sub = ocr(bb, 6)
        txt = cls + " || " + sub
        cells.append({"rows": rr, "cols": cc, "text": txt})
    head = ocr(im.crop((xs[0], 150, xs[-1], 280)), 7)
    return {"page": path[-6:-4], "header": head, "ncols": nc, "names": names, "cells": cells}

if __name__ == "__main__":
    out = [extract(f) for f in sorted(glob.glob(sys.argv[1] + "/d-*.png"))]
    json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    for p in out: print(p["page"], p["header"], p["ncols"], len(p["names"]), len(p["cells"]))
