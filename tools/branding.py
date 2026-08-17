"""Erzeugt Favicons und das Vorschaubild fuer geteilte Links.

Beide greifen auf die Seitenfarben zurueck; die Schrift ist Bodoni 72 (macOS),
das lokale Gegenstueck zur Bodoni Moda der Website.
"""

import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = "/Users/marcomax/Desktop/Mama Website"
IMAGES = os.path.join(ROOT, "images")

BG = (10, 10, 11)
FG = (236, 230, 218)
MUTED = (139, 131, 120)
EMBER = (216, 97, 60)

DISPLAY = "/System/Library/Fonts/Supplemental/Bodoni 72.ttc"
SANS = "/System/Library/Fonts/Supplemental/Futura.ttc"

ICON_SIZES = [(512, "icon-512.png"), (180, "apple-touch-icon.png"), (32, "favicon-32.png")]

# Werk und Ausschnitt fuer das Vorschaubild (Mitte des Motivs)
SHARE_SOURCE = "4k/nachtskyline.jpg"
SHARE_SIZE = (1200, 630)


def display_font(size, index=0):
    return ImageFont.truetype(DISPLAY, size, index=index)


def centered(draw, box, text, font, fill, tracking=0):
    """Text mittig in box (x0, y0, x1, y1) setzen, optional gesperrt."""
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    ascent, descent = font.getmetrics()

    x = (box[0] + box[2] - total) / 2
    y = (box[1] + box[3] - (ascent + descent)) / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=fill)
        x += w + tracking


def icon(size):
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)

    # feiner Rahmen wie die Linien der Seite
    inset = max(1, round(size * 0.055))
    draw.rectangle(
        [inset, inset, size - inset - 1, size - inset - 1],
        outline=tuple(round(c * 0.28 + b * 0.72) for c, b in zip(FG, BG)),
        width=max(1, round(size / 64)),
    )

    font = display_font(round(size * 0.5))
    centered(draw, (0, -size * 0.03, size, size), "ale", font, FG, tracking=size * 0.006)
    return img


def share_card():
    src = cv2.imread(os.path.join(IMAGES, SHARE_SOURCE))
    w, h = SHARE_SIZE

    scale = max(w / src.shape[1], h / src.shape[0]) * 1.12
    scaled = cv2.resize(src, (round(src.shape[1] * scale), round(src.shape[0] * scale)), interpolation=cv2.INTER_AREA)
    y = (scaled.shape[0] - h) // 2
    x = (scaled.shape[1] - w) // 2
    art = scaled[y:y + h, x:x + w]

    # Verlauf von links: die linke Haelfte traegt den Namen, rechts bleibt die
    # Malerei offen. Erst ab der Mitte laeuft der Schleier aus.
    ramp = np.clip((0.62 - np.linspace(0, 1, w)) / 0.42, 0, 1)[None, :, None]
    canvas = art * (1 - ramp * 0.93) + np.array(BG[::-1], np.float32) * (ramp * 0.93)

    img = Image.fromarray(cv2.cvtColor(np.clip(canvas, 0, 255).astype(np.uint8), cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img)

    draw.text((78, 214), "Andrea", font=display_font(104), fill=FG)
    draw.text((78, 318), "Lerch", font=display_font(104), fill=FG)

    kicker = ImageFont.truetype(SANS, 25)
    x = 82
    for ch in "MALEREI  ·  SPACHTEL  ·  ale":
        draw.text((x, 168), ch, font=kicker, fill=EMBER if ch in "ale" else MUTED)
        x += draw.textlength(ch, font=kicker) + 4.5

    draw.line([(80, 452), (196, 452)], fill=EMBER, width=3)
    draw.text((78, 470), "Werke in 4K", font=ImageFont.truetype(SANS, 30), fill=MUTED)
    return img


def main():
    for size, name in ICON_SIZES:
        path = os.path.join(IMAGES, name)
        icon(size).save(path)
        print(f"{name}: {size}x{size}")

    icon(64).save(os.path.join(ROOT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    print("favicon.ico geschrieben")

    card = share_card()
    card.save(os.path.join(IMAGES, "share.jpg"), "JPEG", quality=88, optimize=True, progressive=True)
    print(f"share.jpg: {card.size[0]}x{card.size[1]}")


if __name__ == "__main__":
    main()
