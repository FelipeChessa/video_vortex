/* VideoVortex — App principal: estado, uploads, formulário, etapas,
 * narração (TTS), salvamento de projetos e integração dos módulos. */
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const $$ = (sel, el) => Array.from((el || document).querySelectorAll(sel));

  const ROOM_OPTIONS = [
    "Sala de estar", "Quarto principal", "Quarto", "Cozinha",
    "Banheiro", "Varanda", "Escritório", "Área externa", "Garagem", "Fachada",
  ];

  const state = {
    step: 1,
    photos: [], // {id,label,empty,cover,dataUrl,img}
    info: {
      titulo: "", tipo: "Apartamento", endereco: "", area: "",
      quartos: "", banheiros: "", vagas: "", preco: "",
      diferenciais: "", corretor: "", contato: "",
    },
    tone: "persuasivo",
    duration: 60,
    variant: 0,
    script: null,
    tab: "full",
    stagingStyle: "moderno",
    stagingOn: true,
    projectId: null,
    projectName: "",
    video: {
      res: "720p", secPerPhoto: 4, withTitle: true,
      withStaging: true, withMusic: true, withCaptions: true,
    },
    recording: false,
    videoUrl: null,
  };

  let uid = 1;
  const nid = () => "p" + Date.now().toString(36) + (uid++);

  // ------------------------- utilidades -----------------------------------
  function toast(msg, ok) {
    const t = $("toast");
    t.textContent = msg;
    t.className = "toast show " + (ok === false ? "err" : "");
    clearTimeout(t._h);
    t._h = setTimeout(() => { t.className = "toast"; }, 2800);
  }

  function download(href, name) {
    const a = document.createElement("a");
    a.href = href;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  function loadImg(photo) {
    return new Promise((resolve) => {
      const img = new Image();
      img.onload = () => { photo.img = img; resolve(); };
      img.onerror = () => resolve();
      img.src = photo.dataUrl;
    });
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ------------------------- etapas ---------------------------------------
  const STEPS = [
    { n: 1, label: "Fotos" },
    { n: 2, label: "Dados" },
    { n: 3, label: "Roteiro" },
    { n: 4, label: "Tour 360°" },
    { n: 5, label: "Vídeo" },
  ];

  function renderStepper() {
    const wrap = $("stepper");
    wrap.innerHTML = "";
    STEPS.forEach((s, i) => {
      if (i > 0) {
        const line = document.createElement("div");
        line.className = "step-line" + (s.n <= state.step ? " done" : "");
        wrap.appendChild(line);
      }
      const b = document.createElement("button");
      b.className = "step " + (s.n < state.step ? "done" : s.n === state.step ? "active" : "");
      b.dataset.step = s.n;
      b.innerHTML = `<span class="dot">${s.n < state.step ? "✓" : s.n}</span><span class="lbl">${s.label}</span>`;
      b.addEventListener("click", () => goStep(s.n));
      wrap.appendChild(b);
    });
  }

  function goStep(n) {
    if (n > 2 && state.photos.length === 0) {
      toast("Adicione ao menos 1 foto para continuar.", false);
      return;
    }
    state.step = Math.max(1, Math.min(5, n));
    $$(".panel").forEach((p) => p.classList.remove("active"));
    $("panel-" + state.step).classList.add("active");
    renderStepper();
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (state.step === 3 && !state.script) regenerateScript();
    if (state.step === 4) initTour();
    if (state.step === 5) refreshVideoSummary();
  }

  // ------------------------- fotos ----------------------------------------
  function addPhotos(files) {
    const list = Array.from(files || []).filter((f) => f.type.startsWith("image/"));
    if (!list.length) {
      toast("Selecione arquivos de imagem.", false);
      return;
    }
    let pending = list.length;
    list.forEach((file, k) => {
      const reader = new FileReader();
      reader.onload = () => {
        const photo = {
          id: nid(),
          dataUrl: reader.result,
          label: ROOM_OPTIONS[(state.photos.length + k) % ROOM_OPTIONS.length],
          empty: false,
          cover: state.photos.length === 0 && k === 0,
        };
        state.photos.push(photo);
        loadImg(photo).then(() => {
          if (--pending === 0) {
            renderPhotos();
            toast(`${list.length} foto(s) adicionada(s).`);
          } else renderPhotos();
        });
      };
      reader.readAsDataURL(file);
    });
  }

  function addDemoPhotos() {
    const demos = window.VVDemo.makeDemoPhotos();
    demos.forEach((d, i) => {
      state.photos.push({
        id: nid(), dataUrl: d.dataUrl, label: d.label,
        empty: d.empty, cover: state.photos.length === 0 && i === 0,
      });
    });
    Promise.all(state.photos.map(loadImg)).then(() => {
      renderPhotos();
      toast("Fotos demonstrativas criadas. Marque quais estão vazias!");
    });
  }

  function renderPhotos() {
    const grid = $("photoGrid");
    $("emptyState").style.display = state.photos.length ? "none" : "flex";
    $("photoCount").textContent = state.photos.length
      ? `${state.photos.length} foto(s) · ${state.photos.filter((p) => p.empty).length} vazia(s) p/ staging`
      : "";
    grid.innerHTML = state.photos.map((p, i) => `
      <div class="photo-card ${p.cover ? "cover" : ""}" data-id="${p.id}">
        <img src="${p.dataUrl}" alt="${esc(p.label)}" />
        ${p.cover ? '<span class="cover-badge">CAPA</span>' : ""}
        <div class="photo-tools">
          <button title="Mover p/ esquerda" data-act="left">←</button>
          <button title="Mover p/ direita" data-act="right">→</button>
          <button title="Definir como capa" data-act="cover">★</button>
          <button title="Remover" data-act="del" class="danger">✕</button>
        </div>
        <div class="photo-meta">
          <select data-field="label">
            ${ROOM_OPTIONS.map((o) => `<option ${o === p.label ? "selected" : ""}>${o}</option>`).join("")}
          </select>
          <label class="check"><input type="checkbox" data-field="empty" ${p.empty ? "checked" : ""} /> Vazio? mobiliar ✨</label>
        </div>
        <span class="order">${i + 1}</span>
      </div>`).join("");
    $$(".photo-card", grid).forEach((card) => {
      const id = card.dataset.id;
      const photo = state.photos.find((p) => p.id === id);
      $$("button", card).forEach((b) => b.addEventListener("click", (e) => {
        e.stopPropagation();
        const act = b.dataset.act;
        const idx = state.photos.indexOf(photo);
        if (act === "del") state.photos.splice(idx, 1);
        if (act === "left" && idx > 0) state.photos.splice(idx - 1, 0, state.photos.splice(idx, 1)[0]);
        if (act === "right" && idx < state.photos.length - 1) state.photos.splice(idx + 1, 0, state.photos.splice(idx, 1)[0]);
        if (act === "cover") state.photos.forEach((p) => (p.cover = p.id === id));
        renderPhotos();
      }));
      const sel = card.querySelector('[data-field="label"]');
      const chk = card.querySelector('[data-field="empty"]');
      sel.addEventListener("change", () => { photo.label = sel.value; });
      chk.addEventListener("change", () => { photo.empty = chk.checked; renderPhotos(); });
    });
  }

  // ------------------------- formulário -----------------------------------
  function bindForm() {
    const map = {
      fTitulo: "titulo", fTipo: "tipo", fEndereco: "endereco", fArea: "area",
      fQuartos: "quartos", fBanheiros: "banheiros", fVagas: "vagas",
      fPreco: "preco", fDiferenciais: "diferenciais", fCorretor: "corretor", fContato: "contato",
    };
    Object.keys(map).forEach((id) => {
      const el = $(id);
      el.value = state.info[map[id]] || "";
      el.addEventListener("input", () => {
        state.info[map[id]] = el.value;
        state.script = null; // invalida roteiro
      });
    });
  }

  // ------------------------- roteiro --------------------------------------
  function regenerateScript() {
    state.variant++;
    state.script = window.VVScript.generate(
      state.info, state.photos, state.tone, state.duration, state.variant
    );
    renderScript();
  }

  function scriptText() {
    if (!state.script) return "";
    const s = state.script;
    if (state.tab === "hook") return s.hook;
    if (state.tab === "caption") return s.caption;
    if (state.tab === "whatsapp") return s.whatsapp;
    return s.full;
  }

  function renderScript() {
    const s = state.script;
    if (!s) return;
    $("scriptOut").value = scriptText();
    $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === state.tab));
    $("scriptMeta").textContent =
      `Tom: ${s.tone} · ~${s.targetSeconds}s de vídeo · ${s.wordCount} palavras · leitura ~${s.readSeconds}s`;
  }

  function speak(text) {
    try {
      speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = "pt-BR";
      u.rate = 1.02;
      const voices = speechSynthesis.getVoices();
      const br = voices.find((v) => /pt[-_]BR/i.test(v.lang));
      if (br) u.voice = br;
      speechSynthesis.speak(u);
    } catch (e) {
      toast("Narração indisponível neste navegador.", false);
    }
  }

  // ------------------------- tour -----------------------------------------
  let viewer = null;
  function initTour() {
    const canvas = $("tourCanvas");
    if (!viewer) {
      viewer = new window.VVTour.Viewer(canvas, {
        onIndex: () => renderThumbs(),
      });
      viewer.start();
    }
    viewer.stagingStyle = state.stagingStyle;
    viewer.stagingOn = state.stagingOn;
    viewer.setPhotos(state.photos);
    renderThumbs();
    $("btnTourPlay").textContent = viewer.playing ? "⏸ Pausar" : "▶ Tour automático";
  }

  function renderThumbs() {
    const box = $("tourThumbs");
    box.innerHTML = "";
    state.photos.forEach((p, i) => {
      const b = document.createElement("button");
      b.className = "thumb" + (viewer && viewer.index === i ? " active" : "");
      b.innerHTML = `<img src="${p.dataUrl}" alt="" /><span>${esc(p.label)}${p.empty ? " ✨" : ""}</span>`;
      b.addEventListener("click", () => { viewer.go(i); renderThumbs(); });
      box.appendChild(b);
    });
    const empty = state.photos.filter((p) => p.empty).length;
    $("tourInfo").textContent = state.photos.length
      ? `${state.photos.length} ambiente(s) · ${empty} com staging virtual${state.stagingOn ? " ativado" : " (desativado)"}`
      : "Nenhuma foto.";
  }

  // ------------------------- vídeo ----------------------------------------
  function videoDims() {
    return state.video.res === "1080p" ? [1920, 1080] : [1280, 720];
  }

  function refreshVideoSummary() {
    const per = state.video.secPerPhoto;
    const total = (state.video.withTitle ? 3 : 0) + per * state.photos.length + 3.5;
    const staged = state.photos.filter((p) => p.empty).length;
    $("videoSummary").innerHTML =
      `🎬 <b>${state.photos.length}</b> cenas · <b>${staged}</b> com staging · ` +
      `duração aprox. <b>${total.toFixed(0)}s</b> · ${state.video.res}`;
    drawVideoPreview();
  }

  function drawVideoPreview() {
    const canvas = $("videoCanvas");
    const [W, H] = videoDims();
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    const g = ctx.createLinearGradient(0, 0, W, H);
    g.addColorStop(0, "#14102b");
    g.addColorStop(1, "#0e7490");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "#fff";
    ctx.textAlign = "center";
    ctx.font = `800 ${Math.round(H * 0.07)}px Inter, system-ui, sans-serif`;
    ctx.fillText(state.info.titulo || "Prévia do vídeo", W / 2, H * 0.44);
    ctx.font = `500 ${Math.round(H * 0.035)}px Inter, system-ui, sans-serif`;
    ctx.fillStyle = "rgba(255,255,255,.75)";
    ctx.fillText("Clique em “Gravar vídeo” para renderizar o tour completo", W / 2, H * 0.54);
  }

  async function recordVideo() {
    if (state.recording) return;
    if (!state.photos.length) {
      toast("Adicione fotos primeiro.", false);
      return;
    }
    if (!state.script) {
      state.script = window.VVScript.generate(state.info, state.photos, state.tone, state.duration, state.variant);
    }
    state.recording = true;
    $("btnRecord").disabled = true;
    $("btnRecord").textContent = "⏺ Gravando…";
    $("recBar").style.width = "0%";
    $("recLabel").textContent = "Renderizando cenas…";
    $("videoResult").style.display = "none";

    const [W, H] = videoDims();
    const canvas = $("videoCanvas");
    canvas.width = W;
    canvas.height = H;

    try {
      const wm = [state.info.corretor, state.info.contato].filter(Boolean).join(" • ");
      const { blob, duration } = await window.VVVideo.render({
        canvas,
        photos: state.photos,
        info: state.info,
        captions: state.video.withCaptions ? state.script.scenes : [],
        secPerPhoto: state.video.secPerPhoto,
        withTitle: state.video.withTitle,
        withStaging: state.video.withStaging,
        stagingStyle: state.stagingStyle,
        watermark: wm,
        withMusic: state.video.withMusic,
        fps: 30,
        onProgress: (p, el, total) => {
          $("recBar").style.width = (p * 100).toFixed(1) + "%";
          $("recLabel").textContent = `Gravando… ${el.toFixed(0)}s / ${total.toFixed(0)}s`;
        },
      });
      if (state.videoUrl) URL.revokeObjectURL(state.videoUrl);
      state.videoUrl = URL.createObjectURL(blob);
      $("videoResult").style.display = "block";
      $("videoPlayer").src = state.videoUrl;
      $("videoMeta").textContent =
        `Vídeo pronto! ${(blob.size / 1024 / 1024).toFixed(1)} MB · ${duration.toFixed(0)}s · formato WebM (abre no Chrome/Edge; converta p/ MP4 no CapCut ou CloudConvert).`;
      $("btnDownloadVideo").onclick = () => download(state.videoUrl, "tour-videovortex.webm");
      $("btnDownloadSRT").onclick = () => {
        const srt = window.VVVideo.srt(state.script.scenes, state.video.withTitle ? 3 : 0, state.video.secPerPhoto);
        const url = URL.createObjectURL(new Blob([srt], { type: "text/plain" }));
        download(url, "tour-videovortex.srt");
        setTimeout(() => URL.revokeObjectURL(url), 4000);
      };
      $("recLabel").textContent = "Concluído ✓";
      toast("Vídeo gerado com sucesso!");
    } catch (err) {
      console.error(err);
      toast("Falha na gravação: " + (err.message || err), false);
      $("recLabel").textContent = "Erro na gravação.";
    } finally {
      state.recording = false;
      $("btnRecord").disabled = false;
      $("btnRecord").textContent = "⏺ Gravar vídeo do tour";
    }
  }

  // ------------------------- projetos (backend) ---------------------------
  async function saveProject() {
    const name = ($("projectName").value || state.info.titulo || "Projeto sem nome").trim();
    const payload = {
      name,
      info: state.info,
      settings: { tone: state.tone, duration: state.duration, stagingStyle: state.stagingStyle, video: state.video },
      script: state.script ? { full: state.script.full, hook: state.script.hook } : {},
      photos: state.photos.map((p) => ({ id: p.id, label: p.label, empty: p.empty, cover: p.cover, dataUrl: p.dataUrl })),
    };
    try {
      let res;
      if (state.projectId) {
        res = await fetch("/api/projects/" + state.projectId, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
      } else {
        res = await fetch("/api/projects", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
      }
      const data = await res.json();
      state.projectId = data.id;
      state.projectName = name;
      toast("Projeto salvo ✓");
      loadProjectList();
    } catch (e) {
      toast("Falha ao salvar. O backend está rodando?", false);
    }
  }

  async function loadProjectList() {
    try {
      const res = await fetch("/api/projects");
      const list = await res.json();
      const sel = $("projectList");
      sel.innerHTML = '<option value="">— Meus projetos salvos —</option>' +
        list.map((p) => `<option value="${p.id}">${esc(p.name)} (${p.photoCount} fotos)</option>`).join("");
    } catch (e) { /* backend fora — ignora */ }
  }

  async function openProject(id) {
    if (!id) return;
    try {
      const res = await fetch("/api/projects/" + id);
      if (!res.ok) throw new Error("404");
      const p = await res.json();
      state.projectId = p.id;
      state.projectName = p.name;
      $("projectName").value = p.name;
      Object.assign(state.info, p.info || {});
      bindFormValues();
      state.photos = (p.photos || []).map((ph) => ({ ...ph }));
      await Promise.all(state.photos.map(loadImg));
      renderPhotos();
      Object.assign(state, {
        tone: (p.settings || {}).tone || "persuasivo",
        duration: (p.settings || {}).duration || 60,
      });
      if (p.settings && p.settings.stagingStyle) {
        state.stagingStyle = p.settings.stagingStyle;
        $("stagingStyle").value = state.stagingStyle;
      }
      if (p.settings && p.settings.video) Object.assign(state.video, p.settings.video);
      $("toneSel").value = state.tone;
      $("durSel").value = String(state.duration);
      state.script = null;
      state.variant = 0;
      toast("Projeto carregado ✓");
      goStep(1);
    } catch (e) {
      toast("Não foi possível abrir o projeto.", false);
    }
  }

  async function deleteProject() {
    const id = $("projectList").value;
    if (!id) return;
    if (!confirm("Excluir este projeto salvo?")) return;
    try {
      await fetch("/api/projects/" + id, { method: "DELETE" });
      if (state.projectId === id) state.projectId = null;
      toast("Projeto excluído.");
      loadProjectList();
    } catch (e) {
      toast("Falha ao excluir.", false);
    }
  }

  function bindFormValues() {
    const map = {
      fTitulo: "titulo", fTipo: "tipo", fEndereco: "endereco", fArea: "area",
      fQuartos: "quartos", fBanheiros: "banheiros", fVagas: "vagas",
      fPreco: "preco", fDiferenciais: "diferenciais", fCorretor: "corretor", fContato: "contato",
    };
    Object.keys(map).forEach((id) => { $(id).value = state.info[map[id]] || ""; });
  }

  // ------------------------- boot -----------------------------------------
  function boot() {
    renderStepper();
    bindForm();
    renderPhotos();

    // upload
    const dz = $("dropzone");
    const fi = $("fileInput");
    $("btnUpload").addEventListener("click", () => fi.click());
    dz.addEventListener("click", (e) => { if (e.target === dz) fi.click(); });
    fi.addEventListener("change", () => { addPhotos(fi.files); fi.value = ""; });
    ["dragover", "dragenter"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("over"); }));
    ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("over"); }));
    dz.addEventListener("drop", (e) => addPhotos(e.dataTransfer.files));
    $("btnDemo").addEventListener("click", addDemoPhotos);
    $("btnClear").addEventListener("click", () => {
      if (state.photos.length && confirm("Remover todas as fotos?")) {
        state.photos = [];
        renderPhotos();
      }
    });

    // navegação
    $$("[data-goto]").forEach((b) => b.addEventListener("click", () => goStep(parseInt(b.dataset.goto, 10))));

    // roteiro
    $("toneSel").addEventListener("change", (e) => { state.tone = e.target.value; state.script = null; regenerateScript(); });
    $("durSel").addEventListener("change", (e) => { state.duration = parseInt(e.target.value, 10); state.script = null; regenerateScript(); });
    $("btnRegen").addEventListener("click", regenerateScript);
    $$(".tab").forEach((t) => t.addEventListener("click", () => { state.tab = t.dataset.tab; renderScript(); }));
    $("btnCopy").addEventListener("click", async () => {
      try { await navigator.clipboard.writeText($("scriptOut").value); toast("Roteiro copiado ✓"); }
      catch (e) { $("scriptOut").select(); document.execCommand("copy"); toast("Roteiro copiado ✓"); }
    });
    $("btnSpeak").addEventListener("click", () => speak($("scriptOut").value));
    $("btnStopSpeak").addEventListener("click", () => { try { speechSynthesis.cancel(); } catch (e) {} });
    $("btnDlScript").addEventListener("click", () => {
      const url = URL.createObjectURL(new Blob([$("scriptOut").value], { type: "text/plain;charset=utf-8" }));
      download(url, "roteiro-videovortex.txt");
      setTimeout(() => URL.revokeObjectURL(url), 4000);
    });

    // tour
    $("btnTourPlay").addEventListener("click", () => {
      if (!viewer) return;
      viewer.playing ? viewer.pause() : viewer.play();
      $("btnTourPlay").textContent = viewer.playing ? "⏸ Pausar" : "▶ Tour automático";
    });
    $("btnTourPrev").addEventListener("click", () => { viewer && viewer.prev(); });
    $("btnTourNext").addEventListener("click", () => { viewer && viewer.next(); });
    $("stagingStyle").addEventListener("change", (e) => {
      state.stagingStyle = e.target.value;
      if (viewer) viewer.stagingStyle = state.stagingStyle;
    });
    $("stagingToggle").addEventListener("change", (e) => {
      state.stagingOn = e.target.checked;
      if (viewer) viewer.stagingOn = state.stagingOn;
      renderThumbs();
    });
    $("compareToggle").addEventListener("change", (e) => {
      if (viewer) viewer.compare = e.target.checked;
    });
    $("tourSpeed").addEventListener("change", (e) => {
      if (viewer) viewer.speed = parseFloat(e.target.value);
    });
    $("btnFullscreen").addEventListener("click", () => {
      const el = $("tourWrap");
      if (document.fullscreenElement) document.exitFullscreen();
      else if (el.requestFullscreen) el.requestFullscreen();
    });

    // vídeo
    $("resSel").addEventListener("change", (e) => { state.video.res = e.target.value; refreshVideoSummary(); });
    $("secSel").addEventListener("change", (e) => { state.video.secPerPhoto = parseFloat(e.target.value); refreshVideoSummary(); });
    [["vTitle", "withTitle"], ["vStaging", "withStaging"], ["vMusic", "withMusic"], ["vCaptions", "withCaptions"]]
      .forEach(([id, key]) => $(id).addEventListener("change", (e) => { state.video[key] = e.target.checked; refreshVideoSummary(); }));
    $("btnRecord").addEventListener("click", recordVideo);

    // projetos
    $("btnSaveProject").addEventListener("click", saveProject);
    $("projectList").addEventListener("change", (e) => openProject(e.target.value));
    $("btnDelProject").addEventListener("click", deleteProject);
    loadProjectList();

    if ("speechSynthesis" in window) speechSynthesis.getVoices();

    // staging fotográfico: carrega layouts + cutouts em segundo plano. Enquanto
    // não chegam, o draw() usa a camada procedural — nada bloqueia a interface.
    if (window.VVStaging && VVStaging.preload) {
      VVStaging.preload().then((ok) => {
        const st = VVStaging.status();
        if (ok && st.ready) console.info(`[VideoVortex] staging fotográfico: ${st.assets}/${st.total} cutouts`);
        else console.info("[VideoVortex] staging fotográfico indisponível — usando a camada procedural");
      });
    }
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
