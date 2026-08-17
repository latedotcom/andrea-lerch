"""Hebt die ausgeschnittenen Gemaelde per Real-ESRGAN auf 4K und legt Web-Groessen an.

Ablauf: Real-ESRGAN x4 -> Lanczos auf Ziellaenge -> lokale Kontrast- und
Detailanhebung -> JPEG-Varianten fuer 4K, Galerie und Kachel-Effekt.
"""

import os
import shutil
import subprocess
import tempfile

import cv2
import numpy as np
from PIL import Image

ROOT = "/Users/marcomax/Desktop/Mama Website/images"
SRC = os.path.join(ROOT, "src")
ESRGAN = "/tmp/resrgan/realesrgan-ncnn-vulkan"
MODEL_DIR = "/tmp/resrgan/models"

TARGETS = {
    "4k": 3840,
    "sharp": 2400,
    "full": 1600,
    "tile": 900,
    "hero": 2560,
}

# Variante -> (Qualitaet, Chroma-Subsampling, progressiv)
ENCODING = {
    "4k": (88, 1, True),
    "sharp": (86, 1, True),
    "full": (84, 2, True),
    "tile": (80, 2, False),
    "hero": (86, 1, True),
}

# Bild fuer den Schrift-Hintergrund im Titel (helles Motiv, damit die Schrift traegt)
HERO_SOURCE = "metropolis"

MASTERS = os.path.join(ROOT, "_master")

NAMES = [
    "mosaikblick",
    "perle",
    "chrysler",
    "gruener-blick",
    "metropolis",
    "hafenlicht",
    "kuppel-triptychon",
    "blauer-turban",
    "nachtskyline",
]


def esrgan(src_path, dst_path, scale=4):
    subprocess.run(
        [
            ESRGAN,
            "-i", src_path,
            "-o", dst_path,
            "-n", "realesrgan-x4plus",
            "-s", str(scale),
            "-m", MODEL_DIR,
            "-f", "png",
        ],
        check=True,
        capture_output=True,
    )


def resize_long_edge(img, target):
    h, w = img.shape[:2]
    scale = target / max(h, w)
    if abs(scale - 1.0) < 0.01:
        return img
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LANCZOS4
    return cv2.resize(img, (int(round(w * scale)), int(round(h * scale))), interpolation=interp)


def enhance(img):
    """Leichte Lokalkontrast- und Detailanhebung, damit die Pastostruktur traegt."""
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=1.25, tileGridSize=(10, 10)).apply(l)
    img = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

    blur = cv2.GaussianBlur(img, (0, 0), 1.4)
    sharp = cv2.addWeighted(img, 1.45, blur, -0.45, 0)

    fine = cv2.GaussianBlur(img, (0, 0), 0.7)
    return cv2.addWeighted(sharp, 0.85, cv2.addWeighted(img, 1.3, fine, -0.3, 0), 0.15, 0)


def save_jpg(img, path, variant):
    quality, subsampling, progressive = ENCODING[variant]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)).save(
        path,
        "JPEG",
        quality=quality,
        optimize=True,
        progressive=progressive,
        subsampling=subsampling,
    )


def hero_fill(master):
    """Fuellung der Titelschrift: helles, breites Band aus dem Werk.

    Die Buchstaben zeigen nur einen kleinen Ausschnitt — dunkle Stellen wirken
    darin schnell matschig, deshalb ein helles Motiv, aufgehellt und satter.
    """
    height, width = master.shape[:2]
    band = master if width > height else master[int(height * 0.16):int(height * 0.60), :]
    band = resize_long_edge(band, TARGETS["hero"])

    hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[..., 1] *= 1.35
    hsv[..., 2] *= 1.16
    return cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR)


def master_for(name, work_dir):
    """Real-ESRGAN nur einmal laufen lassen; danach das Master weiterverwenden."""
    cached = os.path.join(MASTERS, f"{name}.png")
    if os.path.exists(cached):
        return cv2.imread(cached)

    big = os.path.join(work_dir, f"{name}.png")
    esrgan(os.path.join(SRC, f"{name}.png"), big)

    master = enhance(resize_long_edge(cv2.imread(big), TARGETS["4k"]))
    os.makedirs(MASTERS, exist_ok=True)
    cv2.imwrite(cached, master)
    return master


def main():
    work_dir = tempfile.mkdtemp(prefix="upscale-")
    try:
        for name in NAMES:
            master = master_for(name, work_dir)

            save_jpg(master, os.path.join(ROOT, "4k", f"{name}.jpg"), "4k")
            save_jpg(resize_long_edge(master, TARGETS["sharp"]), os.path.join(ROOT, "sharp", f"{name}.jpg"), "sharp")
            save_jpg(resize_long_edge(master, TARGETS["full"]), os.path.join(ROOT, f"{name}.jpg"), "full")
            save_jpg(resize_long_edge(master, TARGETS["tile"]), os.path.join(ROOT, "tile", f"{name}.jpg"), "tile")

            if name == HERO_SOURCE:
                save_jpg(hero_fill(master), os.path.join(ROOT, "hero.jpg"), "hero")

            print(f"{name}: Master {master.shape[1]}x{master.shape[0]}")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
