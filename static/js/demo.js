/* VideoVortex — Fotos demonstrativas procedurais (para testar sem uploads).
 * Desenha 4 ambientes vazios estilizados em canvas e devolve dataURLs. */

(function (global) {
  "use strict";

  function makeCanvas(w, h) {
    const c = document.createElement("canvas");
    c.width = w;
    c.height = h;
    return [c, c.getContext("2d")];
  }

  function roomBase(ctx, W, H, wall, floor, floorDark) {
    const g = ctx.createLinearGradient(0, 0, 0, H * 0.62);
    g.addColorStop(0, wall[0]);
    g.addColorStop(1, wall[1]);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H * 0.62);
    const f = ctx.createLinearGradient(0, H * 0.62, 0, H);
    f.addColorStop(0, floor);
    f.addColorStop(1, floorDark);
    ctx.fillStyle = f;
    ctx.fillRect(0, H * 0.62, W, H * 0.38);
    // tábuas do piso em perspectiva
    ctx.strokeStyle = "rgba(0,0,0,.12)";
    ctx.lineWidth = 2;
    for (let i = 0; i <= 10; i++) {
      const x = (W / 10) * i;
      ctx.beginPath();
      ctx.moveTo(W / 2 + (x - W / 2) * 0.25, H * 0.62);
      ctx.lineTo(x, H);
      ctx.stroke();
    }
    for (let j = 1; j < 4; j++) {
      const y = H * 0.62 + (H * 0.38 * j) / 4;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }
    ctx.fillStyle = "rgba(255,255,255,.55)";
    ctx.fillRect(0, H * 0.62 - 6, W, 6); // rodapé
  }

  function window_(ctx, x, y, w, h, skyA, skyB) {
    ctx.fillStyle = "#fdfdfd";
    ctx.fillRect(x - 10, y - 10, w + 20, h + 20);
    ctx.fillStyle = "#3a3f4a";
    ctx.fillRect(x - 5, y - 5, w + 10, h + 10);
    const sky = ctx.createLinearGradient(0, y, 0, y + h);
    sky.addColorStop(0, skyA);
    sky.addColorStop(1, skyB);
    ctx.fillStyle = sky;
    ctx.fillRect(x, y, w, h);
    // sol + prédios
    ctx.fillStyle = "rgba(255,236,170,.95)";
    ctx.beginPath();
    ctx.arc(x + w * 0.72, y + h * 0.3, w * 0.07, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(70,90,120,.55)";
    [[0.08, 0.45], [0.28, 0.6], [0.5, 0.4]].forEach(([fx, fh]) => {
      ctx.fillRect(x + w * fx, y + h - h * fh, w * 0.16, h * fh);
    });
    ctx.fillStyle = "rgba(255,255,255,.85)";
    ctx.fillRect(x + w / 2 - 3, y, 6, h);
    ctx.fillRect(x, y + h / 2 - 3, w, 6);
    // luz projetada no chão
    ctx.fillStyle = "rgba(255,250,230,.18)";
    ctx.beginPath();
    ctx.moveTo(x, y + h);
    ctx.lineTo(x + w, y + h);
    ctx.lineTo(x + w + 120, y + h + 220);
    ctx.lineTo(x - 60, y + h + 220);
    ctx.closePath();
    ctx.fill();
  }

  function door(ctx, x, y, w, h) {
    ctx.fillStyle = "#7c5230";
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = "#5d3a1e";
    ctx.lineWidth = 6;
    ctx.strokeRect(x, y, w, h);
    ctx.strokeRect(x + 18, y + 22, w - 36, h * 0.38);
    ctx.strokeRect(x + 18, y + h * 0.5, w - 36, h * 0.38);
    ctx.fillStyle = "#e8c15a";
    ctx.beginPath();
    ctx.arc(x + w - 28, y + h * 0.52, 8, 0, Math.PI * 2);
    ctx.fill();
  }

  function pendantLamp(ctx, x, y) {
    ctx.strokeStyle = "#2b2f36";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, y);
    ctx.stroke();
    ctx.fillStyle = "#2b2f36";
    ctx.beginPath();
    ctx.moveTo(x - 46, y + 40);
    ctx.lineTo(x + 46, y + 40);
    ctx.lineTo(x + 24, y);
    ctx.lineTo(x - 24, y);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "rgba(255,220,140,.9)";
    ctx.beginPath();
    ctx.ellipse(x, y + 40, 30, 8, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  function build(label, painter) {
    const W = 1280, H = 800;
    const [c, ctx] = makeCanvas(W, H);
    painter(ctx, W, H);
    return { dataUrl: c.toDataURL("image/jpeg", 0.88), label };
  }

  function living(ctx, W, H) {
    roomBase(ctx, W, H, ["#dfe7ef", "#c3cedb"], "#b98d5f", "#8a6238");
    window_(ctx, W * 0.58, H * 0.1, W * 0.3, H * 0.38, "#7ec8f2", "#d8f0fc");
    door(ctx, W * 0.06, H * 0.18, W * 0.11, H * 0.44);
    pendantLamp(ctx, W * 0.32, H * 0.12);
    // marcas sutis de "vazio": contornos tracejados no chão
    ctx.save();
    ctx.strokeStyle = "rgba(255,255,255,.5)";
    ctx.setLineDash([14, 10]);
    ctx.lineWidth = 3;
    ctx.strokeRect(W * 0.2, H * 0.68, W * 0.4, H * 0.2);
    ctx.restore();
  }

  function bedroom(ctx, W, H) {
    roomBase(ctx, W, H, ["#efe4d6", "#d9c7ae"], "#a87c4f", "#7c5730");
    window_(ctx, W * 0.08, H * 0.1, W * 0.24, H * 0.36, "#8fd0f5", "#e2f3fd");
    door(ctx, W * 0.8, H * 0.18, W * 0.11, H * 0.44);
    pendantLamp(ctx, W * 0.55, H * 0.1);
    ctx.save();
    ctx.strokeStyle = "rgba(255,255,255,.5)";
    ctx.setLineDash([14, 10]);
    ctx.lineWidth = 3;
    ctx.strokeRect(W * 0.4, H * 0.66, W * 0.34, H * 0.22);
    ctx.restore();
  }

  function kitchen(ctx, W, H) {
    roomBase(ctx, W, H, ["#e9eef2", "#ccd6de"], "#9aa4ad", "#6f7982");
    // bancada vazia
    ctx.fillStyle = "#f4f6f8";
    ctx.fillRect(0, H * 0.42, W, H * 0.05);
    ctx.fillStyle = "#5b6472";
    ctx.fillRect(0, H * 0.47, W, H * 0.15);
    ctx.fillStyle = "rgba(255,255,255,.25)";
    for (let i = 1; i < 6; i++) ctx.fillRect((W / 6) * i - 2, H * 0.47, 4, H * 0.15);
    // armários superiores
    ctx.fillStyle = "#dde4ea";
    ctx.fillRect(W * 0.08, H * 0.06, W * 0.5, H * 0.2);
    ctx.fillStyle = "rgba(0,0,0,.08)";
    for (let i = 1; i < 4; i++) ctx.fillRect(W * 0.08 + (W * 0.5 * i) / 4 - 2, H * 0.06, 4, H * 0.2);
    window_(ctx, W * 0.68, H * 0.08, W * 0.24, H * 0.32, "#8fd0f5", "#e2f3fd");
  }

  function balcony(ctx, W, H) {
    // vista aberta
    const sky = ctx.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#6fb9ec");
    sky.addColorStop(0.55, "#cfe9fa");
    sky.addColorStop(0.56, "#9aa4ad");
    sky.addColorStop(1, "#6f7982");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "rgba(255,240,190,.95)";
    ctx.beginPath();
    ctx.arc(W * 0.2, H * 0.22, 44, 0, Math.PI * 2);
    ctx.fill();
    // cidade ao longe
    ctx.fillStyle = "rgba(90,110,140,.7)";
    const rnd = [0.3, 0.5, 0.42, 0.6, 0.36, 0.52, 0.44];
    rnd.forEach((fh, i) => {
      ctx.fillRect(W * 0.05 + i * W * 0.13, H * 0.55 - H * fh * 0.4, W * 0.1, H * fh * 0.4);
    });
    // guarda-corpo de vidro
    ctx.fillStyle = "rgba(220,235,245,.35)";
    ctx.fillRect(0, H * 0.45, W, H * 0.25);
    ctx.fillStyle = "#2b2f36";
    ctx.fillRect(0, H * 0.45 - 8, W, 10);
    for (let i = 0; i <= 8; i++) ctx.fillRect((W / 8) * i - 2, H * 0.45, 4, H * 0.25);
  }

  function makeDemoPhotos() {
    return [
      Object.assign(build("Sala de estar", living), { empty: true }),
      Object.assign(build("Quarto principal", bedroom), { empty: true }),
      Object.assign(build("Cozinha", kitchen), { empty: false }),
      Object.assign(build("Varanda", balcony), { empty: true }),
    ];
  }

  global.VVDemo = { makeDemoPhotos };

})(window);
