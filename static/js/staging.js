/* VideoVortex — Staging virtual.
 *
 * Duas camadas, na mesma chamada:
 *
 *   1. FOTOGRÁFICA (preferida) — compõe *cutouts* fotográficos (PNG com alpha)
 *      dentro do ambiente, com o layout definido em static/assets/layouts.json.
 *   2. PROCEDURAL (fallback)  — desenha mobiliário vetorial no canvas.
 *
 * A escolha é automática: se o layout do ambiente carregou e os PNGs estão
 * prontos, usa a fotográfica; senão, cai na procedural sem quebrar nada. O
 * `draw()` devolve true/false como sempre devolveu.
 *
 * Ponto central do layout: as coordenadas são frações da FOTO (não do canvas).
 * A mobília é dimensionada em múltiplos da altura da foto, então ela anda junto
 * com o fundo quando a panorâmica se move e o zoom muda — sem isso, os móveis
 * deslizam por cima do chão e a colagem fica evidente.
 */

(function (global) {
  "use strict";

  // ---------------------------------------------------------------- estilos
  const STYLES = {
    moderno: {
      label: "Moderno",
      sofa: "#3b5bfd", sofaDark: "#2b44c4", cushion: "#8296ff",
      wood: "#8a5a33", woodDark: "#6e4423", rug: "#e8e4da", rugLine: "#c9c2b2",
      plant: "#2e9e5b", plantDark: "#1f7a42", pot: "#c96f2e",
      lamp: "#ffd166", metal: "#2b2f36", art: ["#3b5bfd", "#ff6b6b", "#ffd166"],
      bed: "#eef1f6", blanket: "#3b5bfd", pillow: "#ffffff",
    },
    minimalista: {
      label: "Minimalista",
      sofa: "#e8e2d6", sofaDark: "#cfc7b4", cushion: "#f7f4ec",
      wood: "#c9a876", woodDark: "#a9855a", rug: "#f3efe6", rugLine: "#d8d0bd",
      plant: "#6aa86f", plantDark: "#4c8551", pot: "#b0a696",
      lamp: "#f4ead2", metal: "#8b8b8b", art: ["#d8d0bd", "#b0a696", "#8b8b8b"],
      bed: "#f7f4ec", blanket: "#d8d0bd", pillow: "#ffffff",
    },
    rustico: {
      label: "Rústico",
      sofa: "#8a5a33", sofaDark: "#6e4423", cushion: "#d9b382",
      wood: "#5d3a1a", woodDark: "#422712", rug: "#c57b4a", rugLine: "#8a4f2b",
      plant: "#3f7a3a", plantDark: "#2c5a28", pot: "#7a4a21",
      lamp: "#ffbe5c", metal: "#3a2a1a", art: ["#8a5a33", "#3f7a3a", "#d9b382"],
      bed: "#e9d9c2", blanket: "#8a4f2b", pillow: "#f5ead6",
    },
    luxo: {
      label: "Luxo",
      sofa: "#23262e", sofaDark: "#14161b", cushion: "#c9a227",
      wood: "#4a3220", woodDark: "#332216", rug: "#2c2f38", rugLine: "#c9a227",
      plant: "#1f7a42", plantDark: "#145c30", pot: "#c9a227",
      lamp: "#ffe9a8", metal: "#c9a227", art: ["#c9a227", "#5b6472", "#23262e"],
      bed: "#f1ead9", blanket: "#23262e", pillow: "#fff8e7",
    },
  };

  // Ajuste tonal aplicado ao cutout para o MESMO móvel ler em 4 estilos.
  //
  // Estes valores são usados só enquanto o layouts.json não chegou (o arquivo é
  // a fonte de verdade). Precisam ser IDÊNTICOS aos de "styles" no JSON: o teste
  // test_filtro_e_sombra_por_estilo_js_python_batem roda os dois lados e falha
  // se alguém mexer num só — foi assim que este bloco ficou desatualizado uma vez.
  const FALLBACK_TINTS = {
    moderno: { filter: "saturate(1.06) contrast(1.08)", shadow: 0.34 },
    minimalista: { filter: "saturate(0.50) brightness(1.20) contrast(0.90)", shadow: 0.18 },
    rustico: { filter: "saturate(1.28) sepia(0.38) contrast(1.05) brightness(0.93)", shadow: 0.4 },
    luxo: { filter: "saturate(1.14) contrast(1.24) brightness(0.76)", shadow: 0.46 },
  };

  const LAYOUT_URL = "/static/assets/layouts.json";
  const ASSET_URL = "/static/assets/";

  // RNG com seed (variações estáveis por foto)
  function rng(seed) {
    let s = (seed % 2147483647) || 1;
    return function () {
      s = (s * 16807) % 2147483647;
      return (s - 1) / 2147483646;
    };
  }

  function rr(ctx, x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function shadow(ctx, blur, color) {
    ctx.shadowBlur = blur;
    ctx.shadowColor = color || "rgba(0,0,0,.35)";
    ctx.shadowOffsetY = blur * 0.25;
  }
  function noShadow(ctx) {
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;
  }

  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }

  /* ==========================================================================
   * 1. CAMADA FOTOGRÁFICA
   * ======================================================================== */

  let LAYOUTS = null;          // conteúdo de layouts.json depois do fetch
  let loadPromise = null;      // promessa única de preload()
  const IMGS = {};             // nome do asset -> HTMLImageElement
  let FILTER_OK = null;        // ctx.filter é suportado?

  /** Aplica aspecto + espelhamento do cutout, respeitando o alpha. */
  function flip(ctx, on) {
    if (!on) return;
    ctx.translate(1, 0);
    ctx.scale(-1, 1);
  }

  /**
   * Projeta a foto no canvas do mesmo jeito que o fundo é desenhado
   * ("cover": preenche o canvas, corta as sobras, desloca no eixo X).
   *
   * Precisa bater EXATAMENTE com o desenho do fundo em tour.js/video.js —
   * é o que garante que a mobília não desgrude do chão.
   *
   * @returns {{dx:number, dy:number, scale:number, iw:number, ih:number}}
   */
  function coverProjection(img, W, H, zoom, offsetX) {
    const iw = (img && (img.naturalWidth || img.width)) || W;
    const ih = (img && (img.naturalHeight || img.height)) || H;
    const base = Math.max(W / iw, H / ih);
    const scale = base * (zoom || 1);
    const dw = iw * scale;
    const dh = ih * scale;
    const maxOff = Math.max(0, (dw - W) / 2);
    const dx = (W - dw) / 2 + clamp(offsetX || 0, -maxOff, maxOff);
    const dy = (H - dh) / 2;
    return { dx: dx, dy: dy, scale: scale, iw: iw, ih: ih, dw: dw, dh: dh, W: W, H: H };
  }

  /** Projeção "modo canvas": a foto É o canvas (sem pan/zoom). */
  function canvasProjection(W, H) {
    return { dx: 0, dy: 0, scale: 1, iw: W, ih: H, dw: W, dh: H, W: W, H: H };
  }

  /**
   * Retângulo final do objeto no canvas, em pixels.
   *
   * h e bottom/top são frações da ALTURA DA FOTO; x é fração da largura da foto.
   * A largura vem do aspecto real do PNG, então nunca há duas medidas para
   * manter em sincronia.
   *
   * @param {object} pl    placement do layouts.json
   * @param {object} dims  {w, h} naturais do PNG
   * @param {object} proj  saída de coverProjection/canvasProjection
   * @returns {{cx:number, top:number, w:number, h:number, bottom:number}}
   */
  function frameOf(pl, dims, proj) {
    const s = proj.scale;
    const h = (pl.h || 0.25) * proj.ih * s;
    const w = h * ((dims && dims.w ? dims.w : 1) / (dims && dims.h ? dims.h : 1));
    const cx = proj.dx + pl.x * proj.iw * s;

    // Duas contas só, mas com nomes que documentam a intenção no layout:
    //   ceiling / wall  → `top`    = onde começa o objeto, medido do alto
    //   floor / surface → `bottom` = onde o objeto encosta, medido do alto
    // (o anchor mora nos metadados do ASSET; ver placementsFor)
    const anchor = pl.anchor || "floor";
    const hangs = anchor === "ceiling" || anchor === "wall";
    let top = hangs
      ? proj.dy + (pl.top || 0) * proj.ih * s
      : proj.dy + (pl.bottom || 0.85) * proj.ih * s - h;

    // Escapa do quadro se a foto for mais larga que o canvas (aí a base do
    // objeto cai fora com o zoom do tour). Objeto cortado na borda lê como
    // defeito; subir alguns pixels não. Devolve `clamped` para quem quiser saber.
    const H = proj.H || 0;
    let clamped = false;
    if (H && !hangs && top + h > H) {
      top = H - h;
      clamped = true;
    }
    return { cx: cx, top: top, w: w, h: h, bottom: top + h, clamped: clamped };
  }

  /** O objeto aparece no canvas? (fora de quadro = não desenha) */
  function visible(frame, W) {
    const m = frame.w * 0.5;
    return frame.cx + frame.w / 2 > -m && frame.cx - frame.w / 2 < W + m;
  }

  /**
   * Monta a string de ctx.filter para o estilo + profundidade.
   * Objeto longe perde contraste e ganha um leve desfoque (haze) — é o que
   * evita o efeito "adesivo colado" numa composição fotográfica.
   */
  function filterFor(styleKey, depth, supported) {
    const tint = (LAYOUTS && LAYOUTS.styles && LAYOUTS.styles[styleKey]) || FALLBACK_TINTS[styleKey];
    if (!supported) return "";
    const parts = [];
    const f = (tint && tint.filter) || "";
    if (f) parts.push(f);
    const d = typeof depth === "number" ? depth : 0.7;
    if (d < 0.5) parts.push("blur(" + ((0.5 - d) * 1.6).toFixed(2) + "px)");
    return parts.join(" ");
  }

  function shadowAmount(styleKey, depth) {
    const tint = (LAYOUTS && LAYOUTS.styles && LAYOUTS.styles[styleKey]) || FALLBACK_TINTS[styleKey];
    const base = (tint && tint.shadow) || 0.3;
    const d = typeof depth === "number" ? depth : 0.7;
    return base * clamp(0.35 + d * 0.75, 0, 1.2);
  }

  /** ctx.filter existe e funciona neste navegador? (Safari antigo não tem) */
  function filtersSupported(ctx) {
    if (FILTER_OK !== null) return FILTER_OK;
    try {
      const prev = ctx.filter;
      ctx.filter = "blur(1px)";
      FILTER_OK = ctx.filter === "blur(1px)";
      ctx.filter = prev === undefined ? "none" : prev;
    } catch (e) {
      FILTER_OK = false;
    }
    return FILTER_OK;
  }

  /** Sombra de contato: mancha elíptica difusa sob o móvel, no chão dele. */
  function contactShadow(ctx, frame, amount) {
    if (!(amount > 0.02)) return;
    const rx = frame.w * 0.46;
    const ry = Math.max(3, frame.w * 0.075);
    ctx.save();
    ctx.translate(frame.cx, frame.bottom);
    ctx.scale(1, ry / rx);
    const g = ctx.createRadialGradient(0, 0, rx * 0.15, 0, 0, rx);
    g.addColorStop(0, "rgba(0,0,0," + (0.42 * amount).toFixed(3) + ")");
    g.addColorStop(0.6, "rgba(0,0,0," + (0.2 * amount).toFixed(3) + ")");
    g.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(0, 0, rx, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  /** O placement está desenhável (imagem carregada e layout válido)? */
  function assetOf(pl) {
    const meta = LAYOUTS && LAYOUTS.assets && LAYOUTS.assets[pl.asset];
    if (!meta) return null;
    const img = IMGS[meta.file];
    if (!img) return null;
    const w = img.naturalWidth || img.width || 0;
    const h = img.naturalHeight || img.height || 0;
    if (!w || !h) return null;
    return { img: img, meta: meta, dims: { w: w, h: h } };
  }

  /** Placements de um ambiente, ordenados do fundo para a frente. */
  function placementsFor(room, styleKey) {
    const roomDef = LAYOUTS && LAYOUTS.rooms && LAYOUTS.rooms[room];
    if (!roomDef || roomDef.photo === false) return null;
    const list = roomDef.placements || [];
    const out = [];
    for (let i = 0; i < list.length; i++) {
      const pl = list[i];
      const styleOverride = pl.styles && pl.styles[styleKey];
      const merged = styleOverride ? Object.assign({}, pl, styleOverride) : pl;
      const asset = assetOf(merged);
      if (!asset) return null; // falta um PNG: cai para a procedural inteira
      // o anchor (floor/wall/ceiling/surface) descreve o ASSET, não o uso: sem
      // este merge, um quadro pendurado seria desenhado no chão.
      if (!merged.anchor && asset.meta && asset.meta.anchor) merged.anchor = asset.meta.anchor;
      out.push({ pl: merged, asset: asset, depth: typeof pl.depth === "number" ? pl.depth : 0.7, i: i });
    }
    out.sort(function (a, b) {
      return a.depth - b.depth || a.i - b.i;
    });
    return out;
  }

  function hasPhotoLayout(room, styleKey) {
    return !!placementsFor(room, styleKey);
  }

  /**
   * Desenha a camada fotográfica.
   * @param {object} o opções já normalizadas de draw()
   * @returns {boolean} true se desenhou
   */
  function drawPhotographic(ctx, W, H, o) {
    if (!LAYOUTS) return false;
    const layers = placementsFor(o.room, o.style);
    if (!layers || !layers.length) return false;

    const proj = o.scene
      ? coverProjection(o.scene.img, W, H, o.scene.zoom, o.scene.offsetX)
      : canvasProjection(W, H);
    if (o.proj) Object.assign(proj, o.proj);

    const useFilter = filtersSupported(ctx);
    for (let k = 0; k < layers.length; k++) {
      const layer = layers[k];
      const pl = layer.pl;
      const frame = frameOf(pl, layer.asset.dims, proj);
      if (!visible(frame, W)) continue;

      ctx.save();
      ctx.globalAlpha = clamp(o.alpha, 0, 1) * (pl.depth < 0.35 ? 0.94 : 1);
      contactShadow(ctx, frame, shadowAmount(o.style, pl.depth));
      if (useFilter) ctx.filter = filterFor(o.style, pl.depth, true);
      if (pl.flip) {
        ctx.translate(frame.cx * 2, 0);
        ctx.scale(-1, 1);
      }
      ctx.drawImage(layer.asset.img, frame.cx - frame.w / 2, frame.top, frame.w, frame.h);
      ctx.restore();
    }
    return true;
  }

  /** Carrega o layouts.json e todos os PNGs uma única vez. */
  function preload() {
    if (loadPromise) return loadPromise;
    if (typeof fetch !== "function" || typeof Image !== "function") {
      loadPromise = Promise.resolve(false);
      return loadPromise;
    }
    loadPromise = fetch(LAYOUT_URL, { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("layouts.json: HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        LAYOUTS = data;
        const files = {};
        const assets = (data && data.assets) || {};
        Object.keys(assets).forEach(function (k) {
          if (assets[k] && assets[k].file) files[assets[k].file] = true;
        });
        const names = Object.keys(files);
        return Promise.all(
          names.map(function (name) {
            return new Promise(function (resolve) {
              const img = new Image();
              img.onload = function () {
                IMGS[name] = img;
                resolve(true);
              };
              img.onerror = function () {
                resolve(false); // sem este PNG: o ambiente que usa ele cai na procedural
              };
              img.src = ASSET_URL + name;
            });
          })
        ).then(function () {
          return true;
        });
      })
      .catch(function () {
        LAYOUTS = null;
        return false;
      });
    return loadPromise;
  }

  /** O que já está pronto — para a interface e para os testes. */
  function status() {
    const assets = (LAYOUTS && LAYOUTS.assets) || {};
    const names = Object.keys(assets).map(function (k) {
      return assets[k].file;
    });
    const loaded = names.filter(function (n) {
      const img = IMGS[n];
      return !!(img && (img.naturalWidth || img.width));
    });
    return {
      layouts: !!LAYOUTS,
      assets: loaded.length,
      total: names.length,
      ready: !!LAYOUTS && loaded.length === names.length,
      photoRooms: LAYOUTS
        ? Object.keys(LAYOUTS.rooms).filter(function (r) {
            return LAYOUTS.rooms[r].photo !== false;
          })
        : [],
    };
  }

  function tintOf(styleKey) {
    return (LAYOUTS && LAYOUTS.styles && LAYOUTS.styles[styleKey]) || FALLBACK_TINTS[styleKey] || FALLBACK_TINTS.moderno;
  }

  /* ==========================================================================
   * 2. CAMADA PROCEDURAL (fallback — nada aqui mudou de comportamento)
   * ======================================================================== */

  function drawRug(ctx, cx, cy, rx, ry, pal) {
    ctx.save();
    ctx.globalAlpha = 0.92;
    shadow(ctx, 24);
    ctx.fillStyle = pal.rug;
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
    ctx.fill();
    noShadow(ctx);
    ctx.strokeStyle = pal.rugLine;
    ctx.lineWidth = Math.max(2, ry * 0.06);
    ctx.beginPath();
    ctx.ellipse(cx, cy, rx * 0.78, ry * 0.68, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
  }

  function drawSofa(ctx, x, y, w, h, pal) {
    ctx.save();
    shadow(ctx, 22);
    ctx.fillStyle = pal.sofaDark;
    rr(ctx, x, y + h * 0.28, w, h * 0.62, h * 0.16);
    ctx.fill(); // base
    ctx.fillStyle = pal.sofa;
    rr(ctx, x + w * 0.03, y, w * 0.94, h * 0.5, h * 0.14);
    ctx.fill(); // encosto
    noShadow(ctx);
    // braços
    ctx.fillStyle = pal.sofaDark;
    rr(ctx, x - w * 0.02, y + h * 0.22, w * 0.12, h * 0.68, h * 0.08);
    ctx.fill();
    rr(ctx, x + w * 0.9, y + h * 0.22, w * 0.12, h * 0.68, h * 0.08);
    ctx.fill();
    // almofadas
    ctx.fillStyle = pal.cushion;
    const cw = w * 0.26;
    for (let i = 0; i < 3; i++) {
      rr(ctx, x + w * 0.09 + i * w * 0.27, y + h * 0.12, cw, h * 0.34, h * 0.08);
      ctx.fill();
      rr(ctx, x + w * 0.09 + i * w * 0.27, y + h * 0.5, cw, h * 0.16, h * 0.06);
      ctx.fill();
    }
    // pés
    ctx.fillStyle = pal.metal;
    [[0.06], [0.9]].forEach(function (a) {
      ctx.fillRect(x + w * a[0], y + h * 0.9, w * 0.04, h * 0.12);
    });
    ctx.restore();
  }

  function drawArmchair(ctx, x, y, w, h, pal) {
    ctx.save();
    shadow(ctx, 18);
    ctx.fillStyle = pal.sofa;
    rr(ctx, x, y + h * 0.25, w, h * 0.65, h * 0.18);
    ctx.fill();
    ctx.fillStyle = pal.sofaDark;
    rr(ctx, x + w * 0.08, y, w * 0.84, h * 0.45, h * 0.16);
    ctx.fill();
    noShadow(ctx);
    ctx.fillStyle = pal.cushion;
    rr(ctx, x + w * 0.2, y + h * 0.12, w * 0.6, h * 0.26, h * 0.1);
    ctx.fill();
    rr(ctx, x + w * 0.16, y + h * 0.52, w * 0.68, h * 0.2, h * 0.08);
    ctx.fill();
    ctx.restore();
  }

  function drawCoffeeTable(ctx, x, y, w, h, pal) {
    ctx.save();
    shadow(ctx, 14);
    ctx.fillStyle = pal.woodDark;
    [[0.08], [0.84]].forEach(function (a) {
      ctx.fillRect(x + w * a[0], y + h * 0.25, w * 0.08, h * 0.75);
    });
    ctx.fillStyle = pal.wood;
    rr(ctx, x, y, w, h * 0.28, h * 0.08);
    ctx.fill();
    noShadow(ctx);
    // livro + xícara
    ctx.fillStyle = pal.cushion;
    ctx.fillRect(x + w * 0.15, y - h * 0.12, w * 0.3, h * 0.12);
    ctx.fillStyle = pal.metal;
    ctx.beginPath();
    ctx.arc(x + w * 0.68, y - h * 0.05, w * 0.05, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawPlant(ctx, x, y, w, h, pal, R) {
    ctx.save();
    shadow(ctx, 12);
    ctx.fillStyle = pal.pot;
    ctx.beginPath();
    ctx.moveTo(x + w * 0.2, y + h * 0.62);
    ctx.lineTo(x + w * 0.8, y + h * 0.62);
    ctx.lineTo(x + w * 0.68, y + h);
    ctx.lineTo(x + w * 0.32, y + h);
    ctx.closePath();
    ctx.fill();
    noShadow(ctx);
    const cx = x + w / 2, top = y + h * 0.62;
    for (let i = 0; i < 7; i++) {
      const a = -Math.PI / 2 + (i - 3) * 0.32 + (R() - 0.5) * 0.1;
      const len = h * (0.5 + R() * 0.25);
      ctx.strokeStyle = i % 2 ? pal.plant : pal.plantDark;
      ctx.lineWidth = Math.max(2, w * 0.06);
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(cx, top);
      ctx.quadraticCurveTo(
        cx + Math.cos(a) * len * 0.5, top + Math.sin(a) * len * 0.6,
        cx + Math.cos(a) * len, top + Math.sin(a) * len
      );
      ctx.stroke();
      ctx.fillStyle = i % 2 ? pal.plant : pal.plantDark;
      ctx.beginPath();
      ctx.ellipse(cx + Math.cos(a) * len, top + Math.sin(a) * len, w * 0.11, w * 0.07, a, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawFloorLamp(ctx, x, y, w, h, pal, glow) {
    ctx.save();
    if (glow) {
      const g = ctx.createRadialGradient(x + w / 2, y + h * 0.18, 4, x + w / 2, y + h * 0.18, w * 2.2);
      g.addColorStop(0, "rgba(255,225,150,.55)");
      g.addColorStop(1, "rgba(255,225,150,0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(x + w / 2, y + h * 0.18, w * 2.2, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = pal.metal;
    ctx.fillRect(x + w * 0.46, y + h * 0.3, w * 0.08, h * 0.7);
    ctx.beginPath();
    ctx.ellipse(x + w / 2, y + h, w * 0.5, h * 0.05, 0, 0, Math.PI * 2);
    ctx.fill();
    shadow(ctx, 16, "rgba(255,210,120,.8)");
    ctx.fillStyle = pal.lamp;
    ctx.beginPath();
    ctx.moveTo(x + w * 0.1, y + h * 0.34);
    ctx.lineTo(x + w * 0.9, y + h * 0.34);
    ctx.lineTo(x + w * 0.72, y);
    ctx.lineTo(x + w * 0.28, y);
    ctx.closePath();
    ctx.fill();
    noShadow(ctx);
    ctx.restore();
  }

  function drawArt(ctx, x, y, w, h, pal, R) {
    ctx.save();
    shadow(ctx, 10);
    ctx.fillStyle = "#f5f2ea";
    ctx.fillRect(x, y, w, h);
    noShadow(ctx);
    ctx.strokeStyle = pal.metal;
    ctx.lineWidth = Math.max(2, w * 0.04);
    ctx.strokeRect(x, y, w, h);
    const cols = pal.art;
    for (let i = 0; i < 3; i++) {
      ctx.fillStyle = cols[i % cols.length];
      ctx.globalAlpha = 0.85;
      ctx.beginPath();
      ctx.arc(x + w * (0.25 + R() * 0.5), y + h * (0.25 + R() * 0.5), w * (0.12 + R() * 0.12), 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  function drawBed(ctx, x, y, w, h, pal) {
    ctx.save();
    shadow(ctx, 22);
    ctx.fillStyle = pal.woodDark;
    rr(ctx, x, y, w * 0.1, h, h * 0.05);
    ctx.fill(); // cabeceira
    ctx.fillStyle = pal.wood;
    ctx.fillRect(x + w * 0.08, y + h * 0.02, w * 0.03, h * 0.96);
    ctx.fillStyle = pal.bed;
    rr(ctx, x + w * 0.12, y + h * 0.28, w * 0.88, h * 0.62, h * 0.08);
    ctx.fill(); // colchão
    noShadow(ctx);
    ctx.fillStyle = pal.pillow;
    rr(ctx, x + w * 0.15, y + h * 0.32, w * 0.2, h * 0.5, h * 0.08);
    ctx.fill();
    rr(ctx, x + w * 0.37, y + h * 0.32, w * 0.2, h * 0.5, h * 0.08);
    ctx.fill();
    ctx.fillStyle = pal.blanket;
    ctx.globalAlpha = 0.95;
    rr(ctx, x + w * 0.58, y + h * 0.28, w * 0.42, h * 0.62, h * 0.08);
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.fillStyle = pal.woodDark;
    ctx.fillRect(x + w * 0.12, y + h * 0.9, w * 0.88, h * 0.06);
    ctx.restore();
  }

  function drawNightstand(ctx, x, y, w, h, pal, lampOn) {
    ctx.save();
    shadow(ctx, 10);
    ctx.fillStyle = pal.wood;
    rr(ctx, x, y + h * 0.3, w, h * 0.7, w * 0.08);
    ctx.fill();
    noShadow(ctx);
    ctx.strokeStyle = pal.woodDark;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x + w * 0.15, y + h * 0.6);
    ctx.lineTo(x + w * 0.85, y + h * 0.6);
    ctx.stroke();
    ctx.fillStyle = pal.metal;
    ctx.fillRect(x + w * 0.46, y + h * 0.12, w * 0.08, h * 0.2);
    ctx.fillStyle = pal.lamp;
    ctx.beginPath();
    ctx.moveTo(x + w * 0.2, y + h * 0.14);
    ctx.lineTo(x + w * 0.8, y + h * 0.14);
    ctx.lineTo(x + w * 0.68, y);
    ctx.lineTo(x + w * 0.32, y);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  }

  function drawDiningSet(ctx, x, y, w, h, pal) {
    ctx.save();
    shadow(ctx, 16);
    ctx.fillStyle = pal.wood;
    rr(ctx, x, y + h * 0.3, w, h * 0.12, h * 0.04);
    ctx.fill(); // tampo
    ctx.fillStyle = pal.woodDark;
    ctx.fillRect(x + w * 0.1, y + h * 0.42, w * 0.06, h * 0.58);
    ctx.fillRect(x + w * 0.84, y + h * 0.42, w * 0.06, h * 0.58);
    noShadow(ctx);
    ctx.fillStyle = pal.sofa;
    [[-0.02, 1], [0.72, 1]].forEach(function (a) {
      const cx = x + w * a[0];
      rr(ctx, cx, y + h * 0.42, w * 0.26, h * 0.14, h * 0.04);
      ctx.fill();
      ctx.fillRect(cx + w * 0.02, y + h * 0.56, w * 0.04, h * 0.44);
      ctx.fillRect(cx + w * 0.2, y + h * 0.56, w * 0.04, h * 0.44);
    });
    ctx.fillStyle = pal.metal;
    ctx.beginPath();
    ctx.ellipse(x + w * 0.5, y + h * 0.3, w * 0.12, h * 0.05, 0, 0, Math.PI * 2);
    ctx.fill();
    ["#ff6b6b", "#ffd166", "#6aa86f"].forEach(function (c, i) {
      ctx.fillStyle = c;
      ctx.beginPath();
      ctx.arc(x + w * (0.44 + i * 0.06), y + h * 0.26, w * 0.03, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.restore();
  }

  function drawPendant(ctx, x, y, len, pal) {
    ctx.save();
    ctx.strokeStyle = pal.metal;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, y);
    ctx.stroke();
    shadow(ctx, 18, "rgba(255,210,120,.9)");
    ctx.fillStyle = pal.lamp;
    ctx.beginPath();
    ctx.moveTo(x - 26, y + 26);
    ctx.lineTo(x + 26, y + 26);
    ctx.lineTo(x + 14, y - 6);
    ctx.lineTo(x - 14, y - 6);
    ctx.closePath();
    ctx.fill();
    noShadow(ctx);
    const g = ctx.createRadialGradient(x, y + 30, 4, x, y + 30, 120);
    g.addColorStop(0, "rgba(255,225,150,.5)");
    g.addColorStop(1, "rgba(255,225,150,0)");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x, y + 30, 120, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  function drawTowelRack(ctx, x, y, w, h, pal) {
    ctx.save();
    ctx.fillStyle = pal.metal;
    ctx.fillRect(x, y, w * 0.06, h);
    ctx.fillRect(x + w * 0.94, y, w * 0.06, h);
    ctx.fillRect(x, y, w, h * 0.06);
    ["#ffffff", pal.cushion, pal.rugLine].forEach(function (c, i) {
      ctx.fillStyle = c;
      rr(ctx, x + w * (0.1 + i * 0.28), y + h * 0.06, w * 0.24, h * 0.6, 6);
      ctx.fill();
    });
    ctx.restore();
  }

  function drawLightWash(ctx, W, H) {
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, "rgba(255,244,220,.10)");
    g.addColorStop(0.55, "rgba(255,244,220,0)");
    g.addColorStop(1, "rgba(60,40,20,.14)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
  }

  // ---- composições por ambiente ------------------------------------------
  function composeLiving(ctx, W, H, pal, R, full) {
    const horizon = H * 0.62;
    drawRug(ctx, W * 0.46, H * 0.82, W * 0.3, H * 0.11, pal);
    drawSofa(ctx, W * 0.16, horizon - H * 0.2, W * 0.42, H * 0.3, pal);
    drawCoffeeTable(ctx, W * 0.3, H * 0.68, W * 0.2, H * 0.14, pal);
    drawArmchair(ctx, W * 0.62, horizon - H * 0.16, W * 0.16, H * 0.26, pal);
    drawPlant(ctx, W * 0.82, H * 0.42, W * 0.09, H * 0.3, pal, R);
    drawFloorLamp(ctx, W * 0.05, H * 0.3, W * 0.07, H * 0.44, pal, true);
    drawArt(ctx, W * 0.24, H * 0.1, W * 0.13, H * 0.2, pal, R);
    drawArt(ctx, W * 0.4, H * 0.12, W * 0.1, H * 0.15, pal, R);
    if (full) drawPendant(ctx, W * 0.46, H * 0.16, 0, pal);
  }

  function composeBedroom(ctx, W, H, pal, R) {
    drawRug(ctx, W * 0.5, H * 0.85, W * 0.32, H * 0.1, pal);
    drawBed(ctx, W * 0.14, H * 0.38, W * 0.56, H * 0.34, pal);
    drawNightstand(ctx, W * 0.04, H * 0.52, W * 0.08, H * 0.2, pal, true);
    drawNightstand(ctx, W * 0.72, H * 0.52, W * 0.08, H * 0.2, pal, true);
    drawPlant(ctx, W * 0.85, H * 0.45, W * 0.09, H * 0.28, pal, R);
    drawArt(ctx, W * 0.3, H * 0.08, W * 0.18, H * 0.2, pal, R);
    drawFloorLamp(ctx, W * 0.9, H * 0.32, W * 0.05, H * 0.4, pal, false);
  }

  function composeKitchen(ctx, W, H, pal, R) {
    drawDiningSet(ctx, W * 0.24, H * 0.52, W * 0.42, H * 0.32, pal);
    drawRug(ctx, W * 0.45, H * 0.9, W * 0.26, H * 0.07, pal);
    drawPendant(ctx, W * 0.36, H * 0.14, 0, pal);
    drawPendant(ctx, W * 0.54, H * 0.14, 0, pal);
    drawPlant(ctx, W * 0.08, H * 0.5, W * 0.08, H * 0.26, pal, R);
    drawPlant(ctx, W * 0.82, H * 0.5, W * 0.08, H * 0.26, pal, R);
    drawArt(ctx, W * 0.7, H * 0.12, W * 0.12, H * 0.18, pal, R);
  }

  function composeBathroom(ctx, W, H, pal, R) {
    drawTowelRack(ctx, W * 0.62, H * 0.34, W * 0.22, H * 0.4, pal);
    drawPlant(ctx, W * 0.1, H * 0.5, W * 0.09, H * 0.28, pal, R);
    drawArt(ctx, W * 0.3, H * 0.12, W * 0.12, H * 0.18, pal, R);
    ctx.save();
    ctx.fillStyle = "rgba(200,225,235,.5)";
    rr(ctx, W * 0.36, H * 0.3, W * 0.18, H * 0.3, 14);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,.8)";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(W * 0.4, H * 0.55);
    ctx.lineTo(W * 0.48, H * 0.35);
    ctx.stroke();
    ctx.restore();
  }

  function composeOutdoor(ctx, W, H, pal, R) {
    drawRug(ctx, W * 0.45, H * 0.84, W * 0.28, H * 0.1, pal);
    drawArmchair(ctx, W * 0.2, H * 0.48, W * 0.18, H * 0.28, pal);
    drawArmchair(ctx, W * 0.55, H * 0.48, W * 0.18, H * 0.28, pal);
    drawCoffeeTable(ctx, W * 0.4, H * 0.66, W * 0.16, H * 0.13, pal);
    drawPlant(ctx, W * 0.08, H * 0.42, W * 0.1, H * 0.34, pal, R);
    drawPlant(ctx, W * 0.78, H * 0.42, W * 0.1, H * 0.34, pal, R);
    drawFloorLamp(ctx, W * 0.88, H * 0.3, W * 0.06, H * 0.44, pal, true);
  }

  function composeGeneric(ctx, W, H, pal, R) {
    composeLiving(ctx, W, H, pal, R, false);
  }

  const COMPOSERS = {
    sala: composeLiving,
    quarto: composeBedroom,
    cozinha: composeKitchen,
    banheiro: composeBathroom,
    varanda: composeOutdoor,
    area: composeOutdoor,
    escritorio: composeLiving,
    default: composeGeneric,
    fachada: null,
    garagem: null,
  };

  function drawBadge(ctx, W, H, label) {
    ctx.save();
    ctx.font = "600 " + Math.max(13, Math.round(W * 0.016)) + "px Inter, system-ui, sans-serif";
    const tw = ctx.measureText(label).width;
    const bw = tw + 28, bh = Math.max(28, W * 0.032);
    const x = W - bw - 16, y = 16;
    ctx.fillStyle = "rgba(10,10,18,.62)";
    rr(ctx, x, y, bw, bh, bh / 2);
    ctx.fill();
    ctx.strokeStyle = "rgba(255,255,255,.25)";
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = "#ffd166";
    ctx.textBaseline = "middle";
    ctx.fillText(label, x + 14, y + bh / 2 + 1);
    ctx.restore();
  }

  /* ==========================================================================
   * 3. PONTO DE ENTRADA
   * ======================================================================== */

  /**
   * Desenha o staging sobre o contexto (que já contém a foto).
   *
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} W largura do canvas
   * @param {number} H altura do canvas
   * @param {object} opts
   *   style  — moderno | minimalista | rustico | luxo
   *   room   — sala | quarto | cozinha | ... (ver VVScript.detectRoom)
   *   seed   — variação estável (usada só pela camada procedural)
   *   alpha  — opacidade global
   *   badge  — desenha o selo de "simulação"
   *   photo  — false força a camada procedural
   *   scene  — {img, zoom, offsetX} da foto de fundo: amarra a mobília ao
   *            ambiente (sem isso, as coordenadas viram frações do canvas)
   *   proj   — sobrepõe a projeção (usado pelo player de panorama)
   * @returns {boolean} true se desenhou algo
   */
  function drawStaging(ctx, W, H, opts) {
    const o = Object.assign(
      { style: "moderno", room: "default", seed: 7, alpha: 1, badge: true, photo: true,
        scene: null, proj: null },
      opts || {}
    );
    const pal = STYLES[o.style] || STYLES.moderno;

    // 1) tenta a camada fotográfica
    if (o.photo !== false) {
      ctx.save();
      ctx.globalAlpha = clamp(o.alpha, 0, 1);
      drawLightWash(ctx, W, H);
      ctx.restore();
      if (drawPhotographic(ctx, W, H, o)) {
        if (o.badge) drawBadge(ctx, W, H, "✨ Staging: mobília fotográfica");
        return true;
      }
      // não deu: a lavagem de luz já foi aplicada, a procedural entra por cima
      if (o.badge) {
        // segue para a procedural (sem selo duplicado)
      }
    }

    // 2) procedural
    const compose = COMPOSERS[o.room];
    if (!compose) return false;
    const R = rng(o.seed * 9301 + 49297);
    ctx.save();
    ctx.globalAlpha = Math.max(0, Math.min(1, o.alpha));
    if (o.photo === false) drawLightWash(ctx, W, H);
    compose(ctx, W, H, pal, R);
    ctx.restore();
    if (o.badge) drawBadge(ctx, W, H, "✨ Simulação de ambiente mobiliado");
    return true;
  }

  global.VVStaging = {
    draw: drawStaging,
    STYLES: STYLES,
    preload: preload,
    status: status,
    // utilitários puros (usados pelos testes e pelo player de panorama)
    coverProjection: coverProjection,
    canvasProjection: canvasProjection,
    frameOf: frameOf,
    visible: visible,
    filterFor: filterFor,
    shadowAmount: shadowAmount,
    placementsFor: placementsFor,
    hasPhotoLayout: hasPhotoLayout,
    tintOf: tintOf,
    layouts: function () {
      return LAYOUTS;
    },
    _setLayouts: function (data) {
      LAYOUTS = data;
    },
    _setImage: function (file, img) {
      IMGS[file] = img;
    },
  };
})(window);
