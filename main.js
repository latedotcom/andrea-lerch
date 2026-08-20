(() => {
  "use strict";

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const canHover = window.matchMedia("(hover: hover)").matches;

  const clamp = (n, min = 0, max = 1) => Math.min(max, Math.max(min, n));
  const smooth = (t) => t * t * (3 - 2 * t);
  // sehr weiches Ein- und Ausschwingen, ohne Ruck an den Enden
  const smoother = (t) => t * t * t * (t * (t * 6 - 15) + 10);

  const yearEl = document.querySelector("[data-year]");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  /* Intro */
  const intro = document.querySelector("[data-intro]");
  if (intro) {
    setTimeout(() => {
      intro.classList.add("is-done");
      setTimeout(() => intro.classList.add("is-gone"), 600);
    }, reduceMotion ? 0 : 520);
  }

  /* Cursor */
  const cursor = document.querySelector("[data-cursor]");
  if (cursor && canHover) {
    let cx = innerWidth / 2;
    let cy = innerHeight / 2;
    let tx = cx;
    let ty = cy;

    addEventListener("pointermove", (e) => {
      tx = e.clientX;
      ty = e.clientY;
    }, { passive: true });

    const follow = () => {
      cx += (tx - cx) * 0.2;
      cy += (ty - cy) * 0.2;
      cursor.style.translate = `${cx.toFixed(1)}px ${cy.toFixed(1)}px`;
      requestAnimationFrame(follow);
    };
    requestAnimationFrame(follow);

    document.querySelectorAll("a, button, .slide-frame").forEach((el) => {
      el.addEventListener("pointerenter", () => cursor.classList.add("is-big"));
      el.addEventListener("pointerleave", () => cursor.classList.remove("is-big"));
    });
  }

  /* ---------------------------------------------------------------------
     Reel: ein Bild wird weggeschoben, das naechste kommt herein.
     Verschiebungen in Prozent der Bildschirmflaeche.
  --------------------------------------------------------------------- */
  /* Beide Bilder gleiten an: langsam los, langsam ein. Exponenten ueber 1
     sorgen dafuer, dass direkt nach der Standzeit kaum Weg zurueckgelegt wird
     — nichts rastet ein, nichts schiesst herein. */
  /* Auf Touch-Geraeten laenger stehen und trager folgen — ein Finger-Flick
     soll kein Bild ueberspringen. */
  const isTouch = window.matchMedia("(hover: none), (pointer: coarse)").matches;
  const handoff = (d) =>
    d >= 0
      ? Math.pow(d, isTouch ? 1.45 : 1.25)
      : -Math.pow(-d, isTouch ? 1.9 : 1.7);

  const MOVE = {
    // Bild wird zur Seite geschoben, das naechste kommt nach
    push: {
      at: (d, k) => ({ x: k * -92, y: k * -2, s: 1 - Math.abs(d) * 0.07, rot: k * -1.1 }),
      fade: [0.34, 0.52],
    },
    pull: {
      at: (d, k) => ({ x: k * 92, y: k * -2, s: 1 - Math.abs(d) * 0.07, rot: k * 1.1 }),
      fade: [0.34, 0.52],
    },
    rise: {
      at: (d, k) => ({ x: 0, y: k * -92, s: 1 - Math.abs(d) * 0.07, rot: 0 }),
      fade: [0.34, 0.52],
    },
    drop: {
      at: (d, k) => ({ x: 0, y: k * 92, s: 1 - Math.abs(d) * 0.07, rot: 0 }),
      fade: [0.34, 0.52],
    },
  };

  const HOLD = isTouch ? 0.64 : 0.52; // Anteil ohne Bewegung — Touch braucht mehr Stand
  const TAIL = 0.94; // danach bleibt das letzte Bild noch stehen
  const REEL_LERP = isTouch ? 0.045 : 0.075;
  const FLOW_LERP = isTouch ? 0.05 : 0.085;
  /* Pro Frame maximaler Indexsprung: verhindert, dass Momentum mehrere
     Bilder ueberspringt, bevor die Animation sie gezeigt hat. */
  const REEL_MAX_STEP = isTouch ? 0.022 : 0.045;

  const reel = document.querySelector("[data-reel]");
  const slides = [...document.querySelectorAll("[data-slide]")].map((el) => ({
    el,
    copy: el.querySelector("[data-slide-copy]"),
    frame: el.querySelector(".slide-frame"),
    image: el.querySelector("img"),
    move: MOVE[el.dataset.move] ? el.dataset.move : "push",
    hidden: false,
    active: false,
  }));
  const dots = [...document.querySelectorAll("[data-dots] li")];
  const hint = document.querySelector("[data-hint]");
  const last = slides.length - 1;

  let reelTop = 0;
  let reelSpan = 1;
  let shown = 0; // geglaetteter Bildindex mit Standzeiten
  let flow = 0; // geglaetteter Scrollfortschritt ohne Standzeiten
  let dotIndex = -1;
  let hintOn = true;

  const positionFor = (index) => {
    const t = Math.min(index + HOLD * 0.4, last);
    return reelTop + reelSpan * ((t / last) * TAIL);
  };

  const renderReel = (c, flow) => {
    // Beide Bilder eines Wechsels bewegen sich auf derselben Achse,
    // damit nichts uebereinander liegt: Richtung gibt das kommende Bild vor.
    const incoming = Math.min(Math.floor(c + 1e-6) + 1, last);
    const move = MOVE[slides[incoming].move];

    for (let i = 0; i < slides.length; i += 1) {
      const slide = slides[i];
      const d = c - i;
      const ad = Math.abs(d);

      if (ad >= 1.03) {
        if (!slide.hidden) {
          slide.el.style.visibility = "hidden";
          slide.el.style.opacity = "0";
          slide.hidden = true;
        }
        continue;
      }

      if (slide.hidden) {
        slide.el.style.visibility = "";
        slide.hidden = false;
      }

      const o = move.at(d, handoff(d));
      slide.el.style.transform =
        `translate3d(${o.x.toFixed(2)}%, ${o.y.toFixed(2)}%, 0)` +
        ` scale(${o.s.toFixed(4)}) rotate(${o.rot.toFixed(2)}deg)`;
      slide.el.style.opacity = (1 - smoother(clamp((ad - move.fade[0]) / move.fade[1]))).toFixed(3);
      slide.el.style.zIndex = String(60 - Math.round(ad * 20));

      // Auch waehrend der Standzeit ein langsamer Zug nach oben: Scrollen
      // bleibt dadurch immer spuerbar, ohne das Bild aus der Ruhe zu bringen
      const drift = Math.max(-0.5, Math.min(0.5, flow - i));
      if (slide.frame) {
        slide.frame.style.transform = `translate3d(0, ${(-drift * 34).toFixed(1)}px, 0)`;
      }

      if (slide.copy) {
        // Text geht frueh, damit sich beim Wechsel nie zwei Titel begegnen
        slide.copy.style.opacity = (1 - smooth(clamp(ad / 0.26))).toFixed(3);
        slide.copy.style.transform =
          `translate3d(${(o.x * -0.07).toFixed(2)}%, ${(d * 22 - drift * 16).toFixed(1)}px, 0)`;
      }

      const active = ad < 0.3;
      if (active !== slide.active) {
        slide.el.classList.toggle("is-active", active);
        slide.active = active;
      }
    }

    const near = clamp(Math.round(c), 0, last);
    if (near !== dotIndex) {
      dots.forEach((li, i) => li.classList.toggle("is-on", i === near));
      dotIndex = near;
    }

    if (hint) {
      const wantHint = c < 0.12;
      if (wantHint !== hintOn) {
        hint.style.opacity = wantHint ? "1" : "0";
        hintOn = wantHint;
      }
    }
  };

  dots.forEach((li, i) => {
    const button = li.querySelector("button");
    if (button) {
      button.addEventListener("click", () => {
        scrollTo({ top: positionFor(i), behavior: "smooth" });
      });
    }
  });

  /* Weitere Scroll-Momente */
  const panels = [];

  /* spanRatio: Scrollweg als Vielfaches der Fensterhoehe. Ohne Angabe zaehlt der
     Teil des Abschnitts, der ueber das Fenster hinausragt — bei genau einem
     Bildschirm Hoehe waere das null, deshalb die Angabe fuer den Kopfbereich. */
  const registerPanel = (el, apply, spanRatio = 0) => {
    if (el) panels.push({ el, apply, spanRatio, top: 0, height: 0, p: -1 });
  };

  const texturePanel = document.querySelector("[data-texture-panel]");
  const textureCopy = document.querySelector("[data-texture-copy]");
  registerPanel(document.querySelector("[data-texture]"), (p) => {
    if (texturePanel) {
      texturePanel.style.backgroundSize = `${(520 - smooth(p) * 410).toFixed(1)}%`;
      texturePanel.style.backgroundPosition = `${(48 + p * 4).toFixed(1)}% ${(34 + p * 18).toFixed(1)}%`;
    }
    if (textureCopy) {
      const show = smooth(clamp((p - 0.45) / 0.35));
      textureCopy.style.opacity = show.toFixed(3);
      textureCopy.style.transform = `translate3d(0, ${((1 - show) * 40).toFixed(1)}px, 0)`;
    }
  });

  const panoramaImage = document.querySelector("[data-panorama-image]");
  registerPanel(document.querySelector("[data-panorama]"), (p) => {
    if (panoramaImage) {
      const travel = Math.max(panoramaImage.offsetWidth - innerWidth, 0);
      panoramaImage.style.transform = `translate3d(${(-p * travel).toFixed(1)}px, 0, 0)`;
    }
  });

  const heroFragments = document.querySelector("[data-fragments]");
  const heroInner = document.querySelector("[data-hero-inner]");
  registerPanel(document.querySelector("[data-hero]"), (p) => {
    // erst nach einem guten Stueck Scrollen abdunkeln, nicht schon beim ersten Rad-Tick
    const dim = smooth(clamp((p - 0.16) / 0.78));
    if (heroInner) {
      heroInner.style.transform = `translate3d(0, ${(p * -70).toFixed(1)}px, 0)`;
      heroInner.style.opacity = (1 - dim * 0.78).toFixed(3);
    }
    if (heroFragments) {
      heroFragments.style.transform = `translate3d(0, ${(p * 110).toFixed(1)}px, 0)`;
    }
  }, 1);

  /* 4K-Hintergrund der Texturansicht erst kurz vorher laden */
  const textureSection = document.querySelector("[data-texture]");
  if (textureSection && texturePanel && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) {
        texturePanel.style.setProperty("--tex", 'url("images/4k/mosaikblick.jpg")');
        io.disconnect();
      }
    }, { rootMargin: "700px" });
    io.observe(textureSection);
  }

  /* Geometrie einmalig messen, damit die Scroll-Schleife nichts messen muss */
  const measure = () => {
    const y = scrollY;
    if (reel) {
      const rect = reel.getBoundingClientRect();
      reelTop = rect.top + y;
      reelSpan = Math.max(rect.height - innerHeight, 1);
    }
    panels.forEach((panel) => {
      const rect = panel.el.getBoundingClientRect();
      panel.top = rect.top + y;
      panel.height = rect.height;
    });
  };

  measure();
  addEventListener("resize", measure);
  addEventListener("load", measure);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);

  /* Fortschrittsanzeige */
  const progressBar = document.querySelector("[data-progress]");
  const railLabel = document.querySelector("[data-rail-label]");
  const marks = [
    ["#werke", "Werke"],
    ["#textur", "Textur"],
    ["#panorama", "Panorama"],
    ["#ueber", "Über"],
    ["#kontakt", "Kontakt"],
  ].map(([sel, label]) => ({ el: document.querySelector(sel), label }));

  let lastLabel = "";

  const frame = () => {
    const y = scrollY;
    const vh = innerHeight;

    if (reel && !reduceMotion) {
      const raw = clamp((y - reelTop) / reelSpan);
      const t = clamp(raw / TAIL) * last;
      const step = Math.floor(t);
      const f = t - step;
      const target = Math.min(step + (f <= HOLD ? 0 : smoother((f - HOLD) / (1 - HOLD))), last);

      // traeger Nachlauf: das Bild folgt dem Rad, statt daran zu kleben
      const toward = (target - shown) * REEL_LERP;
      shown += Math.sign(toward) * Math.min(Math.abs(toward), REEL_MAX_STEP);
      if (Math.abs(target - shown) < 0.0006) shown = target;

      const towardFlow = (t - flow) * FLOW_LERP;
      flow += Math.sign(towardFlow) * Math.min(Math.abs(towardFlow), REEL_MAX_STEP * 1.2);
      if (Math.abs(t - flow) < 0.0006) flow = t;

      renderReel(shown, flow);
    }

    if (!reduceMotion) {
      for (const panel of panels) {
        if (y + vh < panel.top || y > panel.top + panel.height) continue;
        const span = panel.spanRatio ? panel.spanRatio * vh : Math.max(panel.height - vh, 1);
        const target = clamp((y - panel.top) / span);

        if (panel.p < 0) panel.p = target;
        panel.p += (target - panel.p) * 0.085;
        if (Math.abs(target - panel.p) < 0.0006) panel.p = target;

        panel.apply(panel.p);
      }
    }

    if (progressBar) {
      const max = document.documentElement.scrollHeight - vh;
      progressBar.style.height = `${(clamp(y / Math.max(max, 1)) * 100).toFixed(2)}%`;
    }

    if (railLabel) {
      let label = "Atelier";
      for (const mark of marks) {
        if (mark.el && mark.el.getBoundingClientRect().top <= vh * 0.5) label = mark.label;
      }
      if (label !== lastLabel) {
        railLabel.textContent = label;
        lastLabel = label;
      }
    }

    requestAnimationFrame(frame);
  };

  if (reduceMotion) {
    slides.forEach((slide) => slide.el.classList.add("is-active"));
  }
  requestAnimationFrame(frame);

  /* Leichte Neigung am aktiven Bild */
  if (!reduceMotion && canHover) {
    slides.forEach((slide) => {
      // Neigung liegt auf dem Bild, der Rahmen traegt die Scroll-Drift
      if (!slide.frame || !slide.image) return;
      slide.frame.addEventListener("pointermove", (e) => {
        const rect = slide.frame.getBoundingClientRect();
        const nx = (e.clientX - rect.left) / rect.width - 0.5;
        const ny = (e.clientY - rect.top) / rect.height - 0.5;
        slide.image.style.transform =
          `perspective(1200px) rotateX(${(-ny * 3.4).toFixed(2)}deg) rotateY(${(nx * 5).toFixed(2)}deg)`;
      });
      slide.frame.addEventListener("pointerleave", () => {
        slide.image.style.transform = "";
      });
    });

    if (heroFragments) {
      const figures = [...heroFragments.querySelectorAll("figure")];
      addEventListener("pointermove", (e) => {
        const nx = e.clientX / innerWidth - 0.5;
        const ny = e.clientY / innerHeight - 0.5;
        figures.forEach((fig, i) => {
          const depth = 1 + i * 0.4;
          fig.style.setProperty("--mx", `${(-nx * 40 * depth).toFixed(1)}px`);
          fig.style.setProperty("--my", `${(-ny * 30 * depth).toFixed(1)}px`);
        });
      }, { passive: true });
    }
  }

  /* Lightbox */
  const lightbox = document.querySelector("[data-lightbox]");
  const lightboxImg = document.querySelector("[data-lightbox-img]");
  const lightboxCaption = document.querySelector("[data-lightbox-caption]");

  const closeLightbox = () => {
    lightbox.classList.remove("is-open");
    document.body.style.overflow = "";
    setTimeout(() => {
      lightbox.hidden = true;
      lightboxImg.removeAttribute("src");
    }, 450);
  };

  document.querySelectorAll("[data-zoom]").forEach((button) => {
    button.addEventListener("click", () => {
      const article = button.closest("[data-slide]");
      lightboxImg.src = `images/4k/${button.dataset.zoom}.jpg`;
      lightboxImg.alt = article.querySelector("img").alt;
      lightboxCaption.textContent = `${article.dataset.name} — Andrea Lerch · 4K`;
      lightbox.hidden = false;
      requestAnimationFrame(() => lightbox.classList.add("is-open"));
      document.body.style.overflow = "hidden";
    });
  });

  document.querySelector("[data-lightbox-close]").addEventListener("click", closeLightbox);
  lightbox.addEventListener("click", (e) => {
    if (e.target === lightbox) closeLightbox();
  });
  addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !lightbox.hidden) closeLightbox();
  });
})();
