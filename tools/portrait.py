"""Bereitet das Atelierfoto von Andrea Lerch fuer die Seite auf.

Das Handyfoto ist klein und gegen die Fenster aufgenommen, also von vorn
unterbelichtet. Der Ablauf: Namensschild wegretuschieren -> Farbrauschen
daempfen -> das ganze Bild einmal per Real-ESRGAN vergroessern -> Ausschnitte
-> Gegenlicht ausgleichen -> behutsam nachschaerfen.

Vergroessert wird das vollstaendige Foto, nicht der kleine Ausschnitt: das
Modell hat so mehr Umgebung und trifft Gesichter besser. Ein zweiter Durchgang
waere schaerfer in den Flaechen, buegelt aber Hautstruktur weg und faerbt die
Zaehne — deshalb bleibt es bei einem.

Zwei Ergebnisse: ein nahes Portraet fuer den Kopf der Seite und eine weitere
Ansicht mit Atelier fuer den Ueber-Abschnitt.
"""

import os
import shutil
import tempfile

import cv2
import numpy as np
from PIL import Image

from upscale import esrgan, resize_long_edge

ROOT = "/Users/marcomax/Desktop/Mama Website/images"
SOURCE = os.path.join(ROOT, "src", "andrea-atelier.png")

# Namensschild auf der Brust, in Quellkoordinaten (576 x 1024)
BADGE = (263, 465, 321, 493)

# Mundfeld, ebenfalls in Quellkoordinaten
TEETH = (318, 393, 346, 408)

# Name -> (Ausschnitt links, oben, rechts, unten), Ziel-Langseite, JPEG-Qualitaet
CROPS = {
    "andrea-portrait": ((195, 300, 465, 660), 1440, 91),
    "andrea-atelier": ((40, 205, 505, 790), 1800, 89),
}

ESRGAN_SCALE = 4


def remove_badge(img):
    """Namensschild auf der Brust herausretuschieren."""
    left, top, right, bottom = BADGE
    mask = np.zeros(img.shape[:2], np.uint8)
    mask[top:bottom, left:right] = 255
    return cv2.inpaint(img, mask, 6, cv2.INPAINT_TELEA)


def denoise(img):
    """Nur das Farbrauschen glaetten; die Helligkeit behaelt ihre Zeichnung."""
    ycc = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    y, cr, cb = cv2.split(ycc)
    cr = cv2.medianBlur(cr, 3)
    cb = cv2.medianBlur(cb, 3)
    return cv2.cvtColor(cv2.merge((y, cr, cb)), cv2.COLOR_YCrCb2BGR)


def enlarge(img, work_dir):
    """Das ganze Foto einmal per Real-ESRGAN vergroessern."""
    src = os.path.join(work_dir, "source.png")
    dst = os.path.join(work_dir, "source_x4.png")
    cv2.imwrite(src, img)
    esrgan(src, dst)
    return cv2.imread(dst)


def backlight(img):
    """Gegenlicht ausgleichen: Schatten anheben, Lichter halten."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    norm = l.astype(np.float32) / 255.0
    lifted = np.power(norm, 0.78) * 255.0
    hold = np.clip((norm - 0.72) / 0.28, 0, 1)
    l = (lifted * (1 - hold) + l.astype(np.float32) * hold).astype(np.uint8)

    l = cv2.createCLAHE(clipLimit=1.0, tileGridSize=(8, 8)).apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


def fix_teeth(img, box):
    """Nimmt den Orangestich, den das Gegenlicht in den Mund legt.

    Absichtlich zurueckhaltend: kein Aufhellen zu Weiss, die Zaehne sollen so
    aussehen wie im Foto, nur ohne den Farbstich der Beleuchtung.
    """
    left, top, right, bottom = box
    if right - left < 8 or bottom - top < 6:
        return img

    mask = np.zeros(img.shape[:2], np.float32)
    cv2.ellipse(
        mask,
        ((left + right) // 2, (top + bottom) // 2),
        ((right - left) // 2, (bottom - top) // 2),
        0, 0, 360, 1.0, -1,
    )
    mask = cv2.GaussianBlur(mask, (0, 0), max((right - left) * 0.12, 2.0))

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    l, a, b = cv2.split(lab)

    # nur die helleren Anteile im Mundfeld sind Zaehne, nicht Lippen und Schatten
    region = l[top:bottom, left:right]
    level = np.percentile(region, 70) if region.size else 255.0
    teeth = np.clip((l - level) / 24.0, 0, 1) * mask

    l = l + teeth * 8.0
    a = a - (a - 128.0) * teeth * 0.22
    b = b - (b - 128.0) * teeth * 0.32

    lab = cv2.merge((np.clip(l, 0, 255), np.clip(a, 0, 255), np.clip(b, 0, 255)))
    return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2BGR)


def sharpen(img):
    """Zwei Radien: feine Zeichnung plus etwas Lokalkontrast."""
    fine = cv2.GaussianBlur(img, (0, 0), 0.9)
    img = cv2.addWeighted(img, 1.34, fine, -0.34, 0)

    wide = cv2.GaussianBlur(img, (0, 0), 2.6)
    return cv2.addWeighted(img, 1.12, wide, -0.12, 0)


def main():
    source = cv2.imread(SOURCE)
    if source is None:
        raise SystemExit(f"Quelle fehlt: {SOURCE}")

    source = denoise(remove_badge(source))

    work_dir = tempfile.mkdtemp(prefix="portrait-")
    try:
        big_source = enlarge(source, work_dir)

        for name, (box, target, quality) in CROPS.items():
            left, top, right, bottom = (v * ESRGAN_SCALE for v in box)
            big = resize_long_edge(big_source[top:bottom, left:right], target)

            scale = big.shape[1] / (right - left)
            teeth = tuple(
                int(round(v))
                for v in (
                    (TEETH[0] * ESRGAN_SCALE - left) * scale,
                    (TEETH[1] * ESRGAN_SCALE - top) * scale,
                    (TEETH[2] * ESRGAN_SCALE - left) * scale,
                    (TEETH[3] * ESRGAN_SCALE - top) * scale,
                )
            )

            big = sharpen(fix_teeth(backlight(big), teeth))

            out = os.path.join(ROOT, f"{name}.jpg")
            Image.fromarray(cv2.cvtColor(big, cv2.COLOR_BGR2RGB)).save(
                out, "JPEG", quality=quality, optimize=True, progressive=True, subsampling=1
            )
            print(f"{name}: {big.shape[1]}x{big.shape[0]} — {os.path.getsize(out) // 1024} KB")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
