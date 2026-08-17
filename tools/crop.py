"""Isoliert die Gemaelde aus den Handyfotos.

Pro Foto sind die vier Leinwandecken grob vorgegeben; jede Kante rastet
anschliessend auf das staerkste Gradientenmaximum ein und das Bild wird entzerrt.
"""

import os

import cv2
import numpy as np
from PIL import Image

SRC = "/Users/marcomax/.cursor/projects/Users-marcomax-Desktop-Mama-Website/assets"
OUT = "/Users/marcomax/Desktop/Mama Website/images/src"
DEBUG = "/Users/marcomax/Desktop/Mama Website/tools/_debug"

# name -> (Datei, grobe Ecken TL/TR/BR/BL, Suchradius, Innenversatz, max. Nachtrimmen)
# Nachtrimmen 0 lassen, wenn die Leinwand selbst ruhige Randflaechen hat (Himmel).
WORKS = {
    "mosaikblick": (
        "97ec10be-47fe-41f0-a628-28d4c194a183-6d0d1a7f-91b4-4e91-b8ea-25c3fac67626.png",
        [(4, 10), (820, 8), (820, 1020), (10, 1018)],
        8,
        1,
        0.04,
    ),
    "perle": (
        "IMG_8858-2d83258e-a4e9-4c74-8ca1-84445adb45d2.png",
        [(128, 118), (722, 122), (681, 928), (131, 898)],
        26,
        11,
        0.04,
    ),
    "chrysler": (
        "IMG_8255-83e9ae36-e924-40fc-8fe3-e5048d806030.png",
        [(20, 82), (724, 82), (724, 940), (20, 940)],
        26,
        4,
        0.04,
    ),
    "gruener-blick": (
        "IMG_9218-15a31c47-c957-4176-8921-a6ece5c87c34.png",
        [(105, 270), (631, 276), (636, 910), (97, 916)],
        26,
        4,
        0.04,
    ),
    "metropolis": (
        "IMG_8256-c4bb9caf-7c97-49a8-8cb9-e2045f3450e8.png",
        [(40, 162), (984, 162), (984, 606), (40, 606)],
        24,
        7,
        0.04,
    ),
    "hafenlicht": (
        "IMG_8261_2-d5bd30b2-897a-4403-b564-43b17bff3a2f.png",
        [(48, 352), (668, 348), (668, 868), (48, 872)],
        28,
        6,
        0.0,
    ),
    "kuppel-triptychon": (
        "IMG_8259-f161aff7-5a19-4877-9903-4d984d95b788.png",
        [(38, 285), (700, 268), (700, 890), (38, 908)],
        26,
        4,
        0.02,
    ),
    "blauer-turban": (
        "IMG_8260_2-37523d7d-3f47-4c69-9e1b-153680339925.png",
        [(60, 186), (700, 168), (690, 912), (107, 924)],
        14,
        12,
        0.012,
    ),
    "nachtskyline": (
        "IMG_8262_2-4af946c4-f6c7-46fe-8ed2-b37b0599cb97.png",
        [(74, 241), (967, 214), (963, 644), (78, 655)],
        12,
        6,
        0.0,
    ),
}


# Feinschnitt nach dem Entzerren, falls eine Kante noch Untergrund zeigt:
# name -> (oben, rechts, unten, links) in Pixeln des entzerrten Bildes
CUTS = {
    "hafenlicht": (0, 9, 0, 0),  # Schattenspalt zum Schattenfugenrahmen
    "nachtskyline": (0, 0, 18, 0),  # Leinwand steht auf dem Parkett
}


def gradient_magnitude(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    gx = cv2.Scharr(gray, cv2.CV_32F, 1, 0)
    gy = cv2.Scharr(gray, cv2.CV_32F, 0, 1)
    return cv2.GaussianBlur(np.sqrt(gx * gx + gy * gy), (3, 3), 0)


def sample(grid, points):
    h, w = grid.shape
    xs = np.clip(np.rint(points[:, 0]).astype(int), 0, w - 1)
    ys = np.clip(np.rint(points[:, 1]).astype(int), 0, h - 1)
    return grid[ys, xs]


def refine_edge(grad, p0, p1, search, samples=240):
    """Verschiebt die Kante entlang ihrer Normalen auf das Gradientenmaximum."""
    p0 = np.asarray(p0, dtype=np.float64)
    p1 = np.asarray(p1, dtype=np.float64)
    d = p1 - p0
    length = float(np.hypot(*d))
    u = d / length
    n = np.array([-u[1], u[0]])

    ts = np.linspace(0.06, 0.94, samples)[:, None]
    base = p0[None, :] + ts * d[None, :]

    best_off, best_score = 0.0, -1.0
    for off in np.arange(-search, search + 0.5, 1.0):
        score = float(np.mean(sample(grad, base + off * n)))
        if score > best_score:
            best_score, best_off = score, off

    return p0 + best_off * n, p1 + best_off * n


def line_from(p0, p1):
    p0 = np.asarray(p0, dtype=np.float64)
    d = np.asarray(p1, dtype=np.float64) - p0
    return p0, d / np.hypot(*d)


def intersect(l1, l2):
    (p1, d1), (p2, d2) = l1, l2
    return p1 + np.linalg.solve(np.array([d1, -d2]).T, p2 - p1)[0] * d1


def snap_quad(img, corners, search, rounds=3):
    grad = gradient_magnitude(img)
    quad = [np.asarray(c, dtype=np.float64) for c in corners]

    for _ in range(rounds):
        tl, tr, br, bl = quad
        top = line_from(*refine_edge(grad, tl, tr, search))
        right = line_from(*refine_edge(grad, tr, br, search))
        bottom = line_from(*refine_edge(grad, br, bl, search))
        left = line_from(*refine_edge(grad, bl, tl, search))
        quad = [
            intersect(top, left),
            intersect(top, right),
            intersect(bottom, right),
            intersect(bottom, left),
        ]
        search = max(6, int(search * 0.5))

    return np.array(quad, dtype=np.float32)


def shrink(quad, px):
    """Jede Kante um px entlang ihrer Normalen nach innen versetzen."""
    center = quad.mean(axis=0)
    edges = []
    for i in range(4):
        p0, p1 = quad[i], quad[(i + 1) % 4]
        point, direction = line_from(p0, p1)
        normal = np.array([-direction[1], direction[0]])
        if np.dot(center - point, normal) < 0:
            normal = -normal
        edges.append((point + normal * px, direction))

    return np.array([
        intersect(edges[3], edges[0]),
        intersect(edges[0], edges[1]),
        intersect(edges[1], edges[2]),
        intersect(edges[2], edges[3]),
    ], dtype=np.float32)


def warp(img, quad):
    tl, tr, br, bl = quad
    w = int(round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))))
    h = int(round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))))
    dst = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(quad.astype(np.float32), dst)
    return cv2.warpPerspective(img, matrix, (w, h), flags=cv2.INTER_LANCZOS4)


def band_is_uniform(strip, std_max=10.0):
    lab = cv2.cvtColor(strip, cv2.COLOR_BGR2LAB).astype(np.float32).reshape(-1, 3)
    return float(lab.std(axis=0).mean()) < std_max


def trim_frame(img, max_frac=0.04):
    h, w = img.shape[:2]
    top, left, bottom, right = 0, 0, h, w
    limit_y, limit_x = int(h * max_frac), int(w * max_frac)
    if limit_y < 2 and limit_x < 2:
        return img, (0, 0, 0, 0)

    for _ in range(max(limit_y, limit_x)):
        moved = False
        if top < limit_y and band_is_uniform(img[top:top + 2, left:right]):
            top += 2
            moved = True
        if h - bottom < limit_y and band_is_uniform(img[bottom - 2:bottom, left:right]):
            bottom -= 2
            moved = True
        if left < limit_x and band_is_uniform(img[top:bottom, left:left + 2]):
            left += 2
            moved = True
        if w - right < limit_x and band_is_uniform(img[top:bottom, right - 2:right]):
            right -= 2
            moved = True
        if not moved:
            break

    return img[top:bottom, left:right], (top, left, h - bottom, w - right)


def annotate(name, img, quad):
    vis = img.copy()
    pts = quad.astype(int)
    cv2.polylines(vis, [pts], True, (0, 255, 255), 2)
    for label, p in zip(("TL", "TR", "BR", "BL"), pts):
        cv2.circle(vis, tuple(p), 7, (0, 0, 255), -1)
        cv2.putText(vis, label, (p[0] + 10, p[1] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    scale = 760 / max(vis.shape[:2])
    cv2.imwrite(
        os.path.join(DEBUG, f"{name}_quad.jpg"),
        cv2.resize(vis, (int(vis.shape[1] * scale), int(vis.shape[0] * scale))),
        [int(cv2.IMWRITE_JPEG_QUALITY), 88],
    )


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(DEBUG, exist_ok=True)

    for name, (fname, corners, search, pad, trim) in WORKS.items():
        img = cv2.imread(os.path.join(SRC, fname))
        quad = shrink(snap_quad(img, corners, search), pad)
        annotate(name, img, quad)

        flat = warp(img, quad)
        top, right, bottom, left = CUTS.get(name, (0, 0, 0, 0))
        flat = flat[top:flat.shape[0] - bottom or None, left:flat.shape[1] - right or None]

        cropped, info = trim_frame(flat, trim)
        Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)).save(os.path.join(OUT, f"{name}.png"))

        scale = 760 / max(cropped.shape[:2])
        cv2.imwrite(
            os.path.join(DEBUG, f"{name}_crop.jpg"),
            cv2.resize(cropped, (int(cropped.shape[1] * scale), int(cropped.shape[0] * scale)), interpolation=cv2.INTER_AREA),
            [int(cv2.IMWRITE_JPEG_QUALITY), 92],
        )
        print(f"{name}: {cropped.shape[1]}x{cropped.shape[0]}  nachtrimmen={info}")


if __name__ == "__main__":
    main()
