"""Bereitet das NYC-Nachtfoto fuer den Hero-Bereich auf.

Ablauf: leichtes Denoise -> Real-ESRGAN auf dem ganzen Foto -> Portraet-
Ausschnitt 3:4 um Andrea herum -> leichte Aufhellung und Nachschaerfung.
"""

import os
import shutil
import tempfile

import cv2
import numpy as np
from PIL import Image

from upscale import esrgan, resize_long_edge

ROOT = "/Users/marcomax/Desktop/Mama Website/images"
SOURCE = os.path.join(ROOT, "src", "andrea-nyc.png")

# 3:4-Ausschnitt in Quellkoordinaten (1024 x 719) — Andrea rechts, Skyline links angeschnitten
CROP = (485, 0, 1024, 719)
TARGET = 1440
QUALITY = 91


def denoise(img):
    ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    y, cr, cb = cv2.split(ycc)
    cr = cv2.medianBlur(cr, 3)
    cb = cv2.medianBlur(cb, 3)
    return cv2.cvtColor(cv2.merge((y, cr, cb)), cv2.COLOR_YCrCb2BGR)


def lift(img):
    """Nachtaufnahme etwas oeffnen, ohne die Skyline-Lichter auszubrennen."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    norm = l.astype(np.float32) / 255.0
    lifted = np.power(norm, 0.88) * 255.0
    hold = np.clip((norm - 0.68) / 0.32, 0, 1)
    l = (lifted * (1 - hold) + l.astype(np.float32) * hold).astype(np.uint8)
    l = cv2.createCLAHE(clipLimit=0.9, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def sharpen(img):
    fine = cv2.GaussianBlur(img, (0, 0), 0.9)
    img = cv2.addWeighted(img, 1.28, fine, -0.28, 0)
    wide = cv2.GaussianBlur(img, (0, 0), 2.4)
    return cv2.addWeighted(img, 1.1, wide, -0.1, 0)


def main():
    source = cv2.imread(SOURCE)
    if source is None:
        raise SystemExit(f"Quelle fehlt: {SOURCE}")

    source = denoise(source)
    work_dir = tempfile.mkdtemp(prefix="nyc-")
    try:
        src = os.path.join(work_dir, "source.png")
        dst = os.path.join(work_dir, "source_x4.png")
        cv2.imwrite(src, source)
        esrgan(src, dst)
        big = cv2.imread(dst)

        left, top, right, bottom = (v * 4 for v in CROP)
        crop = big[top:bottom, left:right]
        out_img = sharpen(lift(resize_long_edge(crop, TARGET)))

        out = os.path.join(ROOT, "andrea-portrait.jpg")
        Image.fromarray(cv2.cvtColor(out_img, cv2.COLOR_BGR2RGB)).save(
            out, "JPEG", quality=QUALITY, optimize=True, progressive=True, subsampling=1
        )
        print(f"andrea-portrait: {out_img.shape[1]}x{out_img.shape[0]} — {os.path.getsize(out) // 1024} KB")

        preview = cv2.resize(out_img, (540, 720), interpolation=cv2.INTER_AREA)
        debug = "/Users/marcomax/Desktop/Mama Website/tools/_debug"
        os.makedirs(debug, exist_ok=True)
        cv2.imwrite(os.path.join(debug, "nyc_portrait.jpg"), preview, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
