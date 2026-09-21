/* VideoVortex — Visualizador de tour com simulação de movimento 360°.
 * A foto desliza em panorâmica contínua (ida e volta suave) com leve zoom,
 * transmitindo a sensação de estar girando pelo ambiente. */

(function (global) {
  "use strict";

  function coverDraw(ctx, img, W, H, offsetX, zoom) {
    const iw = img.naturalWidth || img.width;
    const ih = img.naturalHeight || img.height;
    if (!iw || !ih) return;
    const base = Math.max(W / iw, H / ih);
    const scale = base * zoom;
    const dw = iw * scale, dh = ih * scale;
    const maxOff = Math.max(0, (dw - W) / 2);
    const dx = (W - dw) / 2 + Math.max(-maxOff, Math.min(maxOff, offsetX));
    const dy = (H - dh) / 2;
    ctx.drawImage(img, dx, dy, dw, dh);
    return maxOff;
  }

  function vignette(ctx, W, H) {
    const g = ctx.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 0.95);
    g.addColorStop(0, "rgba(0,0,0,0)");
    g.addColorStop(1, "rgba(0,0,0,.42)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
  }

  class TourViewer {
    constructor(canvas, opts) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.photos = [];      // [{id,label,empty,img}]
      this.index = 0;
      this.playing = false;
      this.stagingOn = true;
      this.stagingStyle = "moderno";
      this.compare = false;  // modo antes/depois (metade-metade)
      this.speed = 1;
      this.onIndex = (opts && opts.onIndex) || function () {};
      this._raf = 0;
      this._t0 = 0;
      this._lastSwitch = 0;
      this._fade = 1;        // 1 = imagem atual opaca
      this._prevIndex = -1;
      this._dir = 1;
      this.resize();
    }

    resize() {
      const r = this.canvas.getBoundingClientRect();
      const w = Math.max(320, Math.round(r.width || 960));
      const h = Math.max(200, Math.round(r.width ? r.width * 0.5625 : 540));
      if (this.canvas.width !== w * 2) {
        this.canvas.width = w * 2;
        this.canvas.height = h * 2;
      }
    }

    setPhotos(photos) {
      this.photos = photos || [];
      this.index = 0;
      this._prevIndex = -1;
      this._fade = 1;
      this.render(performance.now());
    }

    go(i) {
      if (!this.photos.length) return;
      const n = this.photos.length;
      const next = ((i % n) + n) % n;
      if (next !== this.index) {
        this._prevIndex = this.index;
        this._fade = 0;
        this.index = next;
        this._lastSwitch = performance.now();
        this._dir = next > this._prevIndex || (this._prevIndex === n - 1 && next === 0) ? 1 : -1;
        this.onIndex(this.index);
      }
    }
    next() { this.go(this.index + 1); }
    prev() { this.go(this.index - 1); }

    play() { this.playing = true; this._lastSwitch = performance.now(); }
    pause() { this.playing = false; }

    start() {
      cancelAnimationFrame(this._raf);
      this._t0 = performance.now();
      this._lastSwitch = performance.now();
      const loop = (now) => {
        this.render(now);
        this._raf = requestAnimationFrame(loop);
      };
      this._raf = requestAnimationFrame(loop);
    }
    stop() { cancelAnimationFrame(this._raf); }

    _drawPhoto(p, W, H, now, fadeAlpha) {
      const ctx = this.ctx;
      ctx.save();
      ctx.globalAlpha = fadeAlpha;
      if (!p || !p.img) {
        ctx.fillStyle = "#151823";
        ctx.fillRect(0, 0, W, H);
        ctx.fillStyle = "#8b93a7";
        ctx.font = "500 28px Inter, system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("Adicione fotos para iniciar o tour", W / 2, H / 2);
        ctx.restore();
        return;
      }
      const t = ((now - this._t0) / 1000) * this.speed;
      const range = W * 0.16;
      const off = Math.sin(t * 0.45) * range * this._dir;
      const zoom = 1.22 + Math.sin(t * 0.3) * 0.03;
      coverDraw(ctx, p.img, W, H, off, zoom);

      const room = (global.VVScript ? global.VVScript.detectRoom(p.label) : "default");
      const wantStaging = this.stagingOn && p.empty && global.VVStaging;
      if (wantStaging && !this.compare) {
        global.VVStaging.draw(ctx, W, H, {
          style: this.stagingStyle, room, seed: this._seedOf(p), alpha: 0.95, badge: true,
        });
      } else if (wantStaging && this.compare) {
        // metade esquerda sem staging, direita com staging
        ctx.save();
        ctx.beginPath();
        ctx.rect(W / 2, 0, W / 2, H);
        ctx.clip();
        global.VVStaging.draw(ctx, W, H, {
          style: this.stagingStyle, room, seed: this._seedOf(p), alpha: 0.95, badge: false,
        });
        ctx.restore();
        ctx.fillStyle = "rgba(255,255,255,.9)";
        ctx.fillRect(W / 2 - 2, 0, 4, H);
        ctx.font = `700 ${Math.round(W * 0.022)}px Inter, system-ui, sans-serif`;
        ctx.fillStyle = "rgba(255,255,255,.95)";
        ctx.textAlign = "left";
        ctx.fillText("ANTES", 24, 48);
        ctx.textAlign = "right";
        ctx.fillText("DEPOIS ✨", W - 24, 48);
      }
      vignette(ctx, W, H);
      ctx.restore();
    }

    _seedOf(p) {
      let s = 7;
      const str = String(p.id || p.label || "x");
      for (let i = 0; i < str.length; i++) s = (s * 31 + str.charCodeAt(i)) % 100000;
      return s;
    }

    _overlay(W, H) {
      const ctx = this.ctx;
      const p = this.photos[this.index];
      // etiqueta do ambiente
      ctx.save();
      const label = p ? (p.label || `Ambiente ${this.index + 1}`) : "—";
      ctx.font = `700 ${Math.round(W * 0.028)}px Inter, system-ui, sans-serif`;
      const tw = ctx.measureText(label).width;
      const bx = 24, by = H - 76, bw = tw + 44, bh = 52;
      ctx.fillStyle = "rgba(8,8,16,.60)";
      ctx.beginPath();
      ctx.roundRect(bx, by, bw, bh, 14);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.textBaseline = "middle";
      ctx.fillText(label, bx + 22, by + bh / 2 + 1);
      // selo 360
      const s = "360°";
      ctx.font = `800 ${Math.round(W * 0.026)}px Inter, system-ui, sans-serif`;
      const sw = ctx.measureText(s).width + 36;
      const grad = ctx.createLinearGradient(W - sw - 24, 0, W - 24, 0);
      grad.addColorStop(0, "#7c3aed");
      grad.addColorStop(1, "#06b6d4");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(W - sw - 24, H - 76, sw, 52, 26);
      ctx.fill();
      ctx.fillStyle = "#fff";
      ctx.textAlign = "center";
      ctx.fillText(s, W - sw / 2 - 24, H - 76 + 27);
      // dots
      const n = this.photos.length;
      if (n > 1) {
        const cy = H - 30, gap = 22;
        const x0 = W / 2 - ((n - 1) * gap) / 2;
        for (let i = 0; i < n; i++) {
          ctx.beginPath();
          ctx.arc(x0 + i * gap, cy, i === this.index ? 7 : 4.5, 0, Math.PI * 2);
          ctx.fillStyle = i === this.index ? "#fff" : "rgba(255,255,255,.4)";
          ctx.fill();
        }
      }
      ctx.restore();
    }

    render(now) {
      this.resize();
      const W = this.canvas.width, H = this.canvas.height;
      const ctx = this.ctx;
      ctx.clearRect(0, 0, W, H);

      if (this.playing && this.photos.length > 1 && now - this._lastSwitch > 6000 / this.speed) {
        this.next();
      }
      if (this._fade < 1) this._fade = Math.min(1, this._fade + 0.045);

      const cur = this.photos[this.index];
      const prev = this.photos[this._prevIndex];
      if (prev && this._fade < 1) this._drawPhoto(prev, W, H, now, 1);
      this._drawPhoto(cur, W, H, now, this._fade < 1 ? this._fade : 1);
      this._overlay(W, H);
    }
  }

  global.VVTour = { Viewer: TourViewer, coverDraw };

})(window);
