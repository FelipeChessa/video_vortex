/* VideoVortex — Estúdio de vídeo.
 * Renderiza o tour em canvas (Ken Burns + transições + staging + legendas),
 * mistura trilha ambiente gerada via WebAudio e grava com MediaRecorder. */

(function (global) {
  "use strict";

  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = src;
    });
  }

  function easeInOut(t) {
    return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
  }

  function drawCoverKenBurns(ctx, img, W, H, progress, dir) {
    const iw = img.naturalWidth || img.width;
    const ih = img.naturalHeight || img.height;
    const base = Math.max(W / iw, H / ih);
    const zoom = base * (1.12 + easeInOut(progress) * 0.14);
    const dw = iw * zoom, dh = ih * zoom;
    const maxOff = Math.max(0, (dw - W) / 2);
    const off = (easeInOut(progress) * 2 - 1) * maxOff * dir;
    ctx.drawImage(img, (W - dw) / 2 + off, (H - dh) / 2, dw, dh);
  }

  function drawTitleCard(ctx, W, H, info, progress) {
    const g = ctx.createLinearGradient(0, 0, W, H);
    g.addColorStop(0, "#14102b");
    g.addColorStop(0.5, "#1e1b4b");
    g.addColorStop(1, "#0e7490");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    // anéis decorativos
    ctx.strokeStyle = "rgba(255,255,255,.08)";
    ctx.lineWidth = 2;
    for (let i = 0; i < 5; i++) {
      ctx.beginPath();
      ctx.arc(W * 0.85, H * 0.15, 60 + i * 46 + progress * 30, 0, Math.PI * 2);
      ctx.stroke();
    }
    const cx = W / 2;
    ctx.textAlign = "center";
    const a = Math.min(1, progress * 3);
    ctx.globalAlpha = a;
    ctx.fillStyle = "#67e8f9";
    ctx.font = `700 ${Math.round(H * 0.045)}px Inter, system-ui, sans-serif`;
    ctx.fillText("TOUR VIRTUAL  •  360°", cx, H * 0.3);
    ctx.fillStyle = "#ffffff";
    ctx.font = `800 ${Math.round(H * 0.1)}px Inter, system-ui, sans-serif`;
    wrapText(ctx, info.titulo || "Imóvel em destaque", cx, H * 0.46, W * 0.86, H * 0.11);
    ctx.fillStyle = "rgba(255,255,255,.85)";
    ctx.font = `500 ${Math.round(H * 0.045)}px Inter, system-ui, sans-serif`;
    ctx.fillText(info.endereco || "", cx, H * 0.66);
    if (info.preco) {
      ctx.font = `800 ${Math.round(H * 0.06)}px Inter, system-ui, sans-serif`;
      ctx.fillStyle = "#ffd166";
      ctx.fillText(info.preco, cx, H * 0.78);
    }
    ctx.globalAlpha = 1;
  }

  function wrapText(ctx, text, cx, y, maxW, lineH) {
    const words = String(text).split(/\s+/);
    const lines = [];
    let line = "";
    words.forEach((w) => {
      const test = line ? line + " " + w : w;
      if (ctx.measureText(test).width > maxW && line) {
        lines.push(line);
        line = w;
      } else line = test;
    });
    if (line) lines.push(line);
    const y0 = y - ((lines.length - 1) * lineH) / 2;
    lines.forEach((l, i) => ctx.fillText(l, cx, y0 + i * lineH));
  }

  function drawCaption(ctx, W, H, text) {
    if (!text) return;
    ctx.save();
    ctx.font = `600 ${Math.round(H * 0.038)}px Inter, system-ui, sans-serif`;
    ctx.textAlign = "center";
    const words = String(text).split(/\s+/);
    const lines = [];
    let line = "";
    words.forEach((w) => {
      const test = line ? line + " " + w : w;
      if (ctx.measureText(test).width > W * 0.86 && line) {
        lines.push(line);
        line = w;
      } else line = test;
    });
    if (line) lines.push(line);
    const shown = lines.slice(-2);
    const lh = H * 0.05;
    const bh = shown.length * lh + H * 0.03;
    const by = H - bh - H * 0.06;
    ctx.fillStyle = "rgba(5,5,12,.66)";
    const bw = W * 0.92;
    ctx.beginPath();
    ctx.roundRect((W - bw) / 2, by, bw, bh, 16);
    ctx.fill();
    ctx.fillStyle = "#fff";
    shown.forEach((l, i) => ctx.fillText(l, W / 2, by + H * 0.035 + lh * (i + 0.75)));
    ctx.restore();
  }

  function drawWatermark(ctx, W, H, text) {
    if (!text) return;
    ctx.save();
    ctx.font = `700 ${Math.round(H * 0.032)}px Inter, system-ui, sans-serif`;
    ctx.textAlign = "right";
    const tw = ctx.measureText(text).width;
    const bw = tw + 32, bh = H * 0.062;
    const x = W - bw - 20, y = 20;
    ctx.fillStyle = "rgba(5,5,12,.55)";
    ctx.beginPath();
    ctx.roundRect(x, y, bw, bh, bh / 2);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.textBaseline = "middle";
    ctx.fillText(text, x + bw - 16, y + bh / 2 + 1);
    ctx.restore();
  }

  function drawRoomTag(ctx, W, H, label, count) {
    ctx.save();
    ctx.font = `700 ${Math.round(H * 0.034)}px Inter, system-ui, sans-serif`;
    ctx.textAlign = "left";
    const text = `${count}  •  ${label}`;
    const tw = ctx.measureText(text).width;
    ctx.fillStyle = "rgba(5,5,12,.55)";
    ctx.beginPath();
    ctx.roundRect(20, 20, tw + 34, H * 0.062, 18);
    ctx.fill();
    ctx.fillStyle = "#67e8f9";
    ctx.textBaseline = "middle";
    ctx.fillText(text, 37, 20 + H * 0.033);
    ctx.restore();
  }

  function drawProgress(ctx, W, H, p) {
    ctx.save();
    ctx.fillStyle = "rgba(255,255,255,.22)";
    ctx.fillRect(0, H - 8, W, 8);
    const g = ctx.createLinearGradient(0, 0, W, 0);
    g.addColorStop(0, "#7c3aed");
    g.addColorStop(1, "#06b6d4");
    ctx.fillStyle = g;
    ctx.fillRect(0, H - 8, W * Math.min(1, p), 8);
    ctx.restore();
  }

  function drawEndCard(ctx, W, H, info, progress) {
    const g = ctx.createLinearGradient(0, 0, W, H);
    g.addColorStop(0, "#0b1020");
    g.addColorStop(1, "#1e1b4b");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.textAlign = "center";
    const a = Math.min(1, progress * 3);
    ctx.globalAlpha = a;
    ctx.fillStyle = "#fff";
    ctx.font = `800 ${Math.round(H * 0.075)}px Inter, system-ui, sans-serif`;
    ctx.fillText("Gostou? Agende sua visita", W / 2, H * 0.4);
    ctx.font = `600 ${Math.round(H * 0.045)}px Inter, system-ui, sans-serif`;
    ctx.fillStyle = "#67e8f9";
    const contact = [info.corretor, info.contato].filter(Boolean).join("  •  ");
    ctx.fillText(contact || "Fale com o corretor", W / 2, H * 0.55);
    if (info.preco) {
      ctx.fillStyle = "#ffd166";
      ctx.font = `800 ${Math.round(H * 0.055)}px Inter, system-ui, sans-serif`;
      ctx.fillText(info.preco, W / 2, H * 0.68);
    }
    ctx.globalAlpha = 1;
  }

  // ---- trilha ambiente (WebAudio, sem arquivos externos) -----------------
  function startAmbientMusic(dest) {
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    const ac = new AC();
    const out = ac.createGain();
    out.gain.value = 0.16;
    const filter = ac.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 900;
    out.connect(filter);
    filter.connect(dest || ac.destination);
    // progressão suave: Am – F – C – G (frequências)
    const chords = [
      [220.0, 261.63, 329.63],
      [174.61, 220.0, 261.63],
      [261.63, 329.63, 392.0],
      [196.0, 246.94, 293.66],
    ];
    let step = 0;
    const oscs = [];
    function playChord() {
      oscs.forEach((o) => { try { o.stop(); } catch (e) {} });
      oscs.length = 0;
      const chord = chords[step % chords.length];
      chord.forEach((f) => {
        const o = ac.createOscillator();
        o.type = "triangle";
        o.frequency.value = f;
        const gn = ac.createGain();
        gn.gain.setValueAtTime(0.0001, ac.currentTime);
        gn.gain.exponentialRampToValueAtTime(0.5, ac.currentTime + 1.5);
        gn.gain.exponentialRampToValueAtTime(0.0001, ac.currentTime + 4.2);
        o.connect(gn);
        gn.connect(out);
        o.start();
        o.stop(ac.currentTime + 4.4);
        oscs.push(o);
      });
      step++;
    }
    playChord();
    const timer = setInterval(playChord, 4000);
    return {
      stop() {
        clearInterval(timer);
        oscs.forEach((o) => { try { o.stop(); } catch (e) {} });
        ac.close().catch(() => {});
      },
    };
  }

  // ---- gravação ----------------------------------------------------------
  async function renderVideo(opts) {
    const {
      canvas, photos, info, scenes, captions,
      secPerPhoto, withTitle, withStaging, stagingStyle,
      watermark, withMusic, fps, onProgress, onDone,
    } = opts;

    const W = canvas.width, H = canvas.height;
    const ctx = canvas.getContext("2d");
    const images = await Promise.all(photos.map((p) => loadImage(p.dataUrl || p.img?.src)));

    const titleDur = withTitle ? 3 : 0;
    const endDur = 3.5;
    const per = Math.max(2, secPerPhoto || 4);
    const total = titleDur + per * photos.length + endDur;

    // áudio
    let music = null, audioDest = null, audioCtx = null;
    if (withMusic) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) {
        audioCtx = new AC();
        await audioCtx.resume().catch(() => {});
        audioDest = audioCtx.createMediaStreamDestination();
        music = startAmbientMusic(audioDest);
      }
    }

    const stream = canvas.captureStream(fps || 30);
    if (audioDest) audioDest.stream.getAudioTracks().forEach((t) => stream.addTrack(t));

    const mimeCandidates = [
      "video/webm;codecs=vp9,opus",
      "video/webm;codecs=vp8,opus",
      "video/webm",
    ];
    const mimeType = mimeCandidates.find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || "";
    const rec = new MediaRecorder(stream, mimeType ? { mimeType, videoBitsPerSecond: 8_000_000 } : undefined);
    const chunks = [];
    rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
    const stopped = new Promise((resolve) => { rec.onstop = resolve; });
    rec.start(250);

    const t0 = performance.now();
    const FADE = 0.7;

    function captionAt(photoIdx, localT) {
      if (!captions || !captions.length) return "";
      const sc = captions.find((c) => c.photoId === photos[photoIdx].id);
      return sc ? sc.text : "";
    }

    function draw(now) {
      const el = (now - t0) / 1000;
      const p = Math.min(1, el / total);
      ctx.clearRect(0, 0, W, H);

      if (el < titleDur && withTitle) {
        drawTitleCard(ctx, W, H, info, el / titleDur);
      } else if (el >= total - endDur) {
        const lp = (el - (total - endDur)) / endDur;
        // funde a última foto para o cartão final
        const lastIdx = photos.length - 1;
        drawCoverKenBurns(ctx, images[lastIdx], W, H, 1, lastIdx % 2 ? -1 : 1);
        ctx.fillStyle = `rgba(8,8,18,${Math.min(1, lp * 2.2)})`;
        ctx.fillRect(0, 0, W, H);
        if (lp > 0.25) {
          ctx.save();
          ctx.globalAlpha = Math.min(1, (lp - 0.25) * 2);
          drawEndCard(ctx, W, H, info, lp);
          ctx.restore();
        }
      } else {
        const tourT = el - titleDur;
        const idx = Math.min(photos.length - 1, Math.floor(tourT / per));
        const local = (tourT - idx * per) / per;
        const dir = idx % 2 === 0 ? 1 : -1;
        drawCoverKenBurns(ctx, images[idx], W, H, local, dir);
        const photo = photos[idx];
        if (withStaging && photo.empty && global.VVStaging && global.VVScript) {
          const room = global.VVScript.detectRoom(photo.label);
          const aIn = Math.min(1, local * 4);
          global.VVStaging.draw(ctx, W, H, {
            style: stagingStyle || "moderno", room, seed: idx * 77 + 13, alpha: 0.95 * aIn, badge: true,
          });
        }
        // vinheta
        const vg = ctx.createRadialGradient(W / 2, H / 2, H * 0.35, W / 2, H / 2, H * 0.95);
        vg.addColorStop(0, "rgba(0,0,0,0)");
        vg.addColorStop(1, "rgba(0,0,0,.35)");
        ctx.fillStyle = vg;
        ctx.fillRect(0, 0, W, H);
        drawRoomTag(ctx, W, H, photo.label || `Ambiente ${idx + 1}`, `${idx + 1}/${photos.length}`);
        drawCaption(ctx, W, H, captionAt(idx, local));
        // transição entre fotos (crossfade simples)
        if (local > 1 - FADE / per && idx < photos.length - 1) {
          const f = (local - (1 - FADE / per)) / (FADE / per);
          ctx.fillStyle = `rgba(5,5,12,${Math.sin(f * Math.PI) * 0.55})`;
          ctx.fillRect(0, 0, W, H);
        }
      }

      if (watermark) drawWatermark(ctx, W, H, watermark);
      drawProgress(ctx, W, H, p);
      if (onProgress) onProgress(p, el, total);
      return el < total;
    }

    await new Promise((resolve) => {
      function frame(now) {
        if (draw(now)) requestAnimationFrame(frame);
        else resolve();
      }
      requestAnimationFrame(frame);
    });

    // fecha com folga de 300ms
    await new Promise((r) => setTimeout(r, 350));
    rec.stop();
    await stopped;
    if (music) music.stop();
    if (audioCtx) audioCtx.close().catch(() => {});

    const blob = new Blob(chunks, { type: "video/webm" });
    if (onDone) onDone(blob, total);
    return { blob, duration: total };
  }

  function buildSRT(scenes, titleDur, per) {
    const pad = (n, l) => String(n).padStart(l || 2, "0");
    function ts(sec) {
      sec = Math.max(0, sec);
      const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
      const s = Math.floor(sec % 60), ms = Math.floor((sec % 1) * 1000);
      return `${pad(h)}:${pad(m)}:${pad(s)},${pad(ms, 3)}`;
    }
    return scenes.map((sc, i) => {
      const start = titleDur + i * per + 0.3;
      const end = titleDur + (i + 1) * per - 0.2;
      return `${i + 1}\n${ts(start)} --> ${ts(end)}\n${sc.label}: ${sc.text}`;
    }).join("\n\n");
  }

  global.VVVideo = { render: renderVideo, srt: buildSRT };

})(window);
