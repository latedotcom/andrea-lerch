# Andrea Lerch — ale

Künstlerische Portfolio-Website für die Malerin Andrea Lerch. Beim Scrollen wird ein Werk
nach dem anderen präsentiert: das aktuelle Bild wird weggeschoben, das nächste rückt nach.
Alle neun Werke liegen in 4K vor.

## Struktur

```
index.html          Seite (Hero, Werke, Textur, Panorama, Über, Kontakt, Lightbox)
styles.css          Gestaltung
main.js             Scroll-Präsentation, Textur-Zoom, Panorama, Cursor, Lightbox
images/             Web-Bilder (1600px Langseite)
images/sharp/       Scharfe Variante für die Präsentation (2400px)
images/hero.jpg     Füllung der Titelschrift (helles Werk, 2560px)
images/andrea-*.jpg Atelierfoto der Künstlerin (Kopf der Seite und Über)
images/4k/          4K-Master für Lightbox, Texturansicht und Panorama
images/tile/        Leichte Variante (900px)
images/src/         Ausgeschnittene Originale, verlustfrei (PNG)
images/_master/     4K-Zwischenstand des Upscalings (nicht ausliefern)
tools/crop.py       Gemälde aus den Handyfotos freistellen
tools/upscale.py    Real-ESRGAN auf 4K + Web-Varianten
tools/portrait.py   Atelierfoto retuschieren, aufhellen, schärfen
```

## Lokal ansehen

```bash
python3 -m http.server 8765
# http://127.0.0.1:8765
```

## Bilder neu aufbereiten

Voraussetzungen: Python 3.9+, `pip install opencv-python-headless numpy pillow` sowie
[Real-ESRGAN (ncnn/Vulkan)](https://github.com/xinntao/Real-ESRGAN/releases) unter
`/tmp/resrgan/` (Pfad in `tools/upscale.py` anpassbar).

```bash
python3 tools/crop.py      # freistellen und entzerren
python3 tools/upscale.py   # auf 4K hochskalieren, Web-Varianten schreiben
python3 tools/portrait.py  # Atelierfoto aufbereiten
```

Die Titelschrift wird mit `HERO_SOURCE` (`tools/upscale.py`) gefüllt — ein helles Werk,
weil dunkle Malerei in den Buchstaben matschig wirkt.

`tools/portrait.py` arbeitet mit Koordinaten des Handyfotos: `BADGE` (Namensschild, wird
wegretuschiert), `TEETH` (wird entfärbt und aufgehellt) und `CROPS` (die beiden
Ausschnitte). Danach folgen Gegenlichtausgleich und Nachschärfung.

`tools/crop.py` enthält pro Foto die vier grob gesetzten Leinwandecken. Jede Kante rastet
automatisch auf das stärkste Gradientenmaximum ein — bei neuen Fotos genügen also grobe
Startwerte im Dictionary `WORKS`. Die letzten beiden Werte je Eintrag sind der Innenversatz
und das maximale Nachtrimmen (bei ruhigen Bildrändern wie Himmel auf `0` setzen, sonst wird
Malerei abgeschnitten). Bleibt an einer Kante Untergrund stehen — Rahmenschatten, Parkett —
hilft ein gezielter Feinschnitt in `CUTS`. Kontrolle über die Debug-Bilder in `tools/_debug/`:
`*_quad.jpg` zeigt die erkannten Ecken, `*_crop.jpg` das Ergebnis.

Nach dem Upscaling liegt ein Master unter `images/_master/`. Solange dieser existiert,
überspringt `tools/upscale.py` den langsamen Real-ESRGAN-Schritt und kodiert nur neu.

## Neues Werk ergänzen

1. Foto nach `assets/` legen und in `WORKS` (`tools/crop.py`) mit groben Ecken eintragen.
2. Denselben Namen in `NAMES` (`tools/upscale.py`) ergänzen, dann `tools/crop.py` und
   `tools/upscale.py` ausführen.
3. In `index.html` einen `<article class="slide">`-Block kopieren und anpassen:
   `data-name`, `data-move`, `--ratio` (Breite / Höhe), `--ar` (Breite ÷ Höhe als Dezimalzahl),
   `srcset` sowie Titel und Text. Zusätzlich einen Punkt in `.reel-dots` ergänzen, die
   Zähler (`01 / 09`) fortschreiben und die Höhe von `.reel` in `styles.css` um etwa
   140svh erhöhen (mobil 125svh).

## Anpassen

- **E-Mail-Adresse**: `hello@andrealerch.art` in `index.html` (Kontakt und Footer-Bereich).
- **Farben und Schriften**: CSS-Variablen am Anfang von `styles.css`.
- **Richtung des Bildwechsels**: `data-move` am `<article>` — `push` (nach links),
  `pull` (nach rechts), `rise` (nach oben), `drop` (nach unten). Die Richtung eines Wechsels
  gibt immer das kommende Bild vor, damit sich Bild und Text nie überlagern.
- **Standzeit je Bild**: `HOLD` in `main.js` (Anteil eines Abschnitts ohne Bewegung, aktuell
  die Hälfte). Wie träge die Bewegung dem Scrollen folgt, steuern die Glättungsfaktoren in
  der Bildschleife (`shown`, `flow`) und bei den Panels.
- **Breites Format**: Klasse `is-wide` am `<article>` stellt Bild über Text.

Reduzierte Bewegung (`prefers-reduced-motion`) wird respektiert: die Werke stehen dann
einfach untereinander.
