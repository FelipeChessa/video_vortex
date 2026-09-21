"""Conferência da geometria do staging: JS (navegador) contra Python (offline).

O problema que este teste resolve: a colocação da mobília só pode ser conferida
de verdade no navegador, e o sandbox não tem navegador. Então a mesma conta é
feita em dois lugares —

    static/js/staging.js          → o que o usuário vê
    tools/preview_staging.py      → o que eu consigo olhar (contact sheet)

Se os dois divergirem, o preview vira ficção: eu aprovo um layout que no
navegador aparece diferente. Estes testes rodam as funções puras do staging.js
no node e comparam com a implementação Python para uma matriz de casos
(zoom do tour, deslocamentos de panorâmica, anchors, aspectos de foto).

Sem node instalado os testes são pulados — não fazem sentido sem ele.
"""

import json
import os
import shutil
import subprocess

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGING_JS = os.path.join(BASE_DIR, "static", "js", "staging.js")
PREVIEW_PY = os.path.join(BASE_DIR, "tools", "preview_staging.py")
ASSETS = os.path.join(BASE_DIR, "static", "assets")

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node não instalado — pulando o cross-check JS/Python"
)

# Script que carrega staging.js num window falso e despeja a geometria em JSON.
# `%(pl)s` entra entre parênteses: um objeto literal solto em posição de
# expressão é lido como bloco pelo parser do JS.
HARNESS = """
global.window = global;
global.document = { createElement: () => ({ getContext: () => null }) };
require(%(js)s);
// coverProjection(img, W, H, zoom, offsetX): a "imagem" só empresta as dimensões.
const proj = VVStaging.coverProjection({ naturalWidth: %(iw)s, naturalHeight: %(ih)s },
                                       %(W)s, %(H)s, %(zoom)s, %(off)s);
const dims = { w: %(aw)s, h: %(ah)s };
const fr = VVStaging.frameOf((%(pl)s), dims, proj);
const cp = VVStaging.canvasProjection(%(W)s, %(H)s);
const fr2 = VVStaging.frameOf((%(pl)s), dims, cp);
console.log(JSON.stringify({
  proj: proj, frame: fr, frame_canvas: fr2,
  visible: VVStaging.visible(fr, %(W)s),
  filter: VVStaging.filterFor(%(style)s, %(depth)s, true),
  shadow: VVStaging.shadowAmount(%(style)s, %(depth)s),
  tint: VVStaging.tintOf(%(style)s)
}));
"""


def _run_js(payload: dict) -> dict:
    script = HARNESS % payload
    res = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        cwd=BASE_DIR,
        timeout=60,
    )
    assert res.returncode == 0, f"node falhou:\n{res.stderr}"
    return json.loads(res.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def py_preview():
    """Importa tools/preview_staging.py como módulo."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("preview_staging", PREVIEW_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def layouts():
    with open(os.path.join(ASSETS, "layouts.json"), encoding="utf-8") as fh:
        return json.load(fh)


# Matriz: canvas 16:9 e 4:3, foto 16:9 (mais larga que o canvas = pior caso),
# zoom do tour (1.22) e 1.0, panorama deslocado para os dois lados.
CASOS = [
    # W, H, iw, ih, zoom, offset
    (1280, 720, 1280, 720, 1.22, 0.0),
    (1280, 720, 1280, 720, 1.22, 120.0),
    (1280, 720, 1280, 720, 1.22, -120.0),
    (1280, 720, 1920, 1080, 1.22, 300.0),
    (1280, 720, 1080, 1350, 1.22, -150.0),
    (1280, 720, 1280, 720, 1.0, 0.0),
    (640, 480, 1280, 720, 1.22, -80.0),
    (960, 540, 4032, 3024, 1.18, 640.0),
]

PLACEMENTS = [
    {"asset": "sofa", "x": 0.42, "bottom": 0.88, "h": 0.20, "anchor": "floor"},
    {"asset": "table-lamp", "x": 0.13, "bottom": 0.755, "h": 0.115, "anchor": "surface"},
    {"asset": "wall-art", "x": 0.42, "top": 0.15, "h": 0.15, "anchor": "wall"},
    {"asset": "pendant", "x": 0.5, "top": 0.02, "h": 0.26, "anchor": "ceiling"},
    {"asset": "vase-decor", "x": 0.28, "bottom": 0.88, "h": 0.115, "anchor": "floor"},
]


@pytest.mark.parametrize(
    "caso",
    CASOS,
    ids=[f"{c[2]}x{c[3]}->{c[0]}x{c[1]}_z{c[4]}_off{c[5]:.0f}" for c in CASOS],
)
def test_frameOf_identico_entre_js_e_python(caso, py_preview, layouts):
    W, H, iw, ih, zoom, off = caso
    asset = layouts["assets"]["sofa"]
    from PIL import Image

    with Image.open(os.path.join(ASSETS, asset["file"])) as im:
        aw, ah = im.size

    for pl in PLACEMENTS:
        payload = dict(
            js=json.dumps(STAGING_JS), W=W, H=H, iw=iw, ih=ih, zoom=zoom, off=off,
            aw=aw, ah=ah, pl=json.dumps(pl),
            style=json.dumps("moderno"), depth=0.7,
        )
        js = _run_js(payload)

        proj_py = py_preview.cover_projection(iw, ih, W, H, zoom, off)
        fr_py = py_preview.frame_of(pl, (aw, ah), proj_py, pl.get("anchor"))

        # projeção
        assert js["proj"]["scale"] == pytest.approx(proj_py["scale"], rel=1e-9)
        assert js["proj"]["dx"] == pytest.approx(proj_py["dx"], rel=1e-9)
        assert js["proj"]["dy"] == pytest.approx(proj_py["dy"], rel=1e-9)

        # quadro final do objeto
        for campo in ("cx", "top", "w", "h", "bottom"):
            assert js["frame"][campo] == pytest.approx(fr_py[campo], rel=1e-6, abs=1e-6), (
                f"{pl['asset']} caso {caso}: campo {campo} divergiu entre JS e Python"
            )


def test_filtro_e_sombra_por_estilo_js_python_batem(py_preview, layouts):
    """O filtro/sombra vem do layouts.json nos dois lados — não pode divergir."""
    for style, defs in layouts["styles"].items():
        js = _run_js(dict(
            js=json.dumps(STAGING_JS), W=1280, H=720, iw=1280, ih=720, zoom=1.22, off=0,
            aw=100, ah=100, pl=json.dumps(PLACEMENTS[0]),
            style=json.dumps(style), depth=0.7,
        ))
        assert js["tint"]["filter"] == defs["filter"], f"filtro divergiu em {style}"
        assert js["tint"]["shadow"] == pytest.approx(defs["shadow"])
        # o filtro precisa realmente incluir o que o layouts.json manda
        assert defs["filter"].split()[0] in js["filter"]


def test_objeto_nao_escapa_pela_base_do_canvas():
    """Regressão: com o zoom do tour, um vaso com bottom alto era cortado.

    Depois do clamp em frameOf, nenhum objeto pode ter o pé abaixo do canvas —
    cortado na borda lê como defeito.
    """
    for bottom in (0.85, 0.88, 0.90, 0.93, 0.98):
        for iw, ih in ((1280, 720), (1920, 1080), (640, 640)):
            js = _run_js(dict(
                js=json.dumps(STAGING_JS), W=1280, H=720, iw=iw, ih=ih, zoom=1.22, off=0,
                aw=260, ah=740,
                pl=json.dumps({"asset": "vase-decor", "x": 0.3, "bottom": bottom, "h": 0.12,
                               "anchor": "floor"}),
                style=json.dumps("moderno"), depth=0.9,
            ))
            assert js["frame"]["bottom"] <= 720 + 1e-6, (
                f"bottom={bottom} foto {iw}x{ih}: objeto escapou a base do canvas"
            )


def test_preload_existe_e_e_idempotente():
    """preload() é chamado no boot: precisa existir e devolver sempre a mesma promessa."""
    script = """
    global.window = global;
    global.document = { createElement: () => ({ getContext: () => null }) };
    require(%s);
    const a = VVStaging.preload();
    const b = VVStaging.preload();
    console.log(JSON.stringify({ same: a === b, isPromise: typeof a.then === 'function',
                                 status: VVStaging.status() }));
    """ % json.dumps(STAGING_JS)
    res = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                         cwd=BASE_DIR, timeout=60)
    assert res.returncode == 0, res.stderr
    out = json.loads(res.stdout.strip().splitlines()[-1])
    assert out["same"] is True, "preload() deveria reaproveitar a promessa"
    assert out["isPromise"] is True
    assert out["status"]["layouts"] is False  # ainda não carregou nada


def test_preload_resolve_os_ambientes_com_anchor_do_asset(layouts):
    """Caminho real do navegador: preload() → placementsFor() com tudo pronto.

    Aqui `fetch` e `Image` são dublados, mas quem decide é o código de produção:
    se o merge do anchor (que descreve o ASSET) para o placement quebrar de novo,
    o quadro volta a ser desenhado no chão e este teste acusa.
    """
    import json as _json
    from PIL import Image as _Image

    dims = {}
    for name, meta in layouts["assets"].items():
        with _Image.open(os.path.join(ASSETS, meta["file"])) as im:
            dims[meta["file"]] = [im.width, im.height]

    script = """
    global.window = global;
    global.document = { createElement: () => ({ getContext: () => null }) };
    const layouts = %(layouts)s;
    const dims = %(dims)s;
    global.fetch = (url) => Promise.resolve({
      ok: true, status: 200, json: () => Promise.resolve(layouts),
    });
    global.Image = class {
      constructor() { this.naturalWidth = 0; this.naturalHeight = 0; }
      set src(v) {
        const d = dims[v.replace('/static/assets/', '')];
        if (!d) { if (this.onerror) this.onerror(); return; }
        this.naturalWidth = d[0]; this.naturalHeight = d[1];
        if (this.onload) this.onload();
      }
    };
    require(%(js)s);
    VVStaging.preload().then((ok) => {
      const st = VVStaging.status();
      const salas = {};
      for (const room of ['sala', 'quarto', 'cozinha', 'escritorio', 'varanda', 'area', 'default']) {
        const layers = VVStaging.placementsFor(room, 'moderno');
        salas[room] = layers && layers.map((l) => ({
          asset: l.pl.asset, anchor: l.pl.anchor, depth: l.depth,
          w: l.asset.dims.w, h: l.asset.dims.h,
        }));
      }
      console.log(JSON.stringify({ ok: ok, status: st, salas: salas }));
    }).catch((e) => { console.log(JSON.stringify({ erro: String(e) })); });
    """ % {"layouts": _json.dumps(layouts), "dims": _json.dumps(dims), "js": _json.dumps(STAGING_JS)}

    res = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                         cwd=BASE_DIR, timeout=90)
    assert res.returncode == 0, f"node falhou:\n{res.stderr}"
    out = _json.loads(res.stdout.strip().splitlines()[-1])
    assert "erro" not in out, out["erro"]

    # tudo carregou: nenhum ambiente cai no fallback procedural
    assert out["ok"] is True
    assert out["status"]["ready"] is True, f"assets incompletos: {out['status']}"
    assert out["status"]["assets"] == out["status"]["total"]

    for room, layers in out["salas"].items():
        esperado = layouts["rooms"][room]
        if esperado.get("photo") is False:
            assert layers is None, f"{room} não deveria ter camada fotográfica"
            continue
        assert layers, f"{room} não resolveu nenhum layer"
        assert len(layers) == len(esperado["placements"]), (
            f"{room}: {len(layers)} layers para {len(esperado['placements'])} placements"
        )
        # anchors vêm dos metadados do asset (o bug que este teste trava)
        for layer in layers:
            assert layer["anchor"], f"{room}/{layer['asset']} sem anchor resolvido"
            assert layer["anchor"] == layouts["assets"][layer["asset"]]["anchor"]
            assert layer["w"] > 0 and layer["h"] > 0
        # ordenados do fundo para a frente
        depths = [l["depth"] for l in layers]
        assert depths == sorted(depths), f"{room}: layers fora de ordem de profundidade"


def test_mobilia_fica_colada_no_piso_durante_a_panoramica(layouts):
    """O ponto central do design: a mobília não pode deslizar sobre o chão.

    Roda o `draw()` de verdade (contexto 2D dublado que registra os drawImage)
    para vários deslocamentos de panorâmica e confere a posição de cada móvel
    **em coordenadas da foto**. Se a posição na foto fica constante enquanto o
    quadro se move, a mobília está amarrada ao ambiente — que é o que faz o tour
    parecer um ambiente de verdade em vez de adesivos colados por cima.

    Cada móvel é identificado pelo ARQUIVO do cutout, não pela ordem do array:
    com a panorâmica deslocada um objeto pode sair de quadro (o culling do
    `visible()` é intencional), e aí os índices deixam de casar entre quadros.
    """
    import json as _json
    from PIL import Image as _Image

    dims = {}
    for name, meta in layouts["assets"].items():
        with _Image.open(os.path.join(ASSETS, meta["file"])) as im:
            dims[meta["file"]] = [im.width, im.height]

    script = """
    global.window = global;
    global.document = { createElement: () => ({ getContext: () => null }) };
    require(%(js)s);

    const layouts = %(layouts)s;
    const dims = %(dims)s;
    VVStaging._setLayouts(layouts);
    for (const name of Object.keys(layouts.assets)) {
      const file = layouts.assets[name].file;
      VVStaging._setImage(file, {
        nome: file,
        naturalWidth: dims[file][0],
        naturalHeight: dims[file][1],
      });
    }

    const chamadas = [];
    const grad = { addColorStop() {} };
    const ctx = {
      filter: 'none', globalAlpha: 1, fillStyle: '', strokeStyle: '', lineWidth: 1,
      shadowBlur: 0, shadowColor: '', shadowOffsetY: 0, font: '', textBaseline: '', textAlign: '',
      save() {}, restore() {}, translate() {}, scale() {}, beginPath() {}, closePath() {},
      arc() {}, ellipse() {}, fill() {}, stroke() {}, fillRect() {}, strokeRect() {},
      moveTo() {}, lineTo() {}, quadraticCurveTo() {}, arcTo() {}, clip() {}, rect() {},
      createLinearGradient: () => grad, createRadialGradient: () => grad,
      measureText: () => ({ width: 100 }), fillText() {},
      drawImage(img, x, y, w, h) { chamadas.push({ nome: img.nome, x: x, y: y, w: w, h: h }); },
    };

    const W = 1280, H = 720, zoom = 1.22;
    const img = { naturalWidth: 1280, naturalHeight: 720, nome: 'FUNDO' };
    const saida = {};
    for (const off of [-160, -80, 0, 80, 160]) {
      chamadas.length = 0;
      const proj = VVStaging.coverProjection(img, W, H, zoom, off);
      VVStaging.draw(ctx, W, H, {
        style: 'moderno', room: 'sala', alpha: 1, badge: false,
        scene: { img: img, zoom: zoom, offsetX: off },
      });
      saida[off] = {};
      for (const c of chamadas) {
        if (c.nome === 'FUNDO') continue;
        saida[off][c.nome] = {
          fx: (c.x - proj.dx) / proj.scale,   // posição convertida para px da FOTO
          fy: (c.y - proj.dy) / proj.scale,
          fw: c.w / proj.scale,
          fh: c.h / proj.scale,
        };
      }
    }
    console.log(JSON.stringify(saida));
    """ % {"js": _json.dumps(STAGING_JS), "layouts": _json.dumps(layouts), "dims": _json.dumps(dims)}

    res = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                         cwd=BASE_DIR, timeout=90)
    assert res.returncode == 0, f"node falhou:\n{res.stderr}"
    por_offset = _json.loads(res.stdout.strip().splitlines()[-1])

    esperados = {layouts["assets"][pl["asset"]]["file"]
                 for pl in layouts["rooms"]["sala"]["placements"]}

    # no quadro central todos os móveis do ambiente aparecem
    assert set(por_offset["0"]) <= esperados
    assert len(por_offset["0"]) >= 5, (
        f"esperava quase todos os móveis no quadro central, veio {sorted(por_offset['0'])}"
    )
    # algum culling nas pontas é esperado (objeto sai de quadro)
    assert len(por_offset["160"]) <= len(por_offset["0"])

    for off, itens in por_offset.items():
        for arquivo, dado in itens.items():
            ref = por_offset["0"].get(arquivo)
            if not ref:
                continue  # só existe nas pontas: nada para comparar
            assert dado["fx"] == pytest.approx(ref["fx"], abs=0.5), (
                f"offset {off}: {arquivo} mudou de lugar NA FOTO em x "
                f"({dado['fx']:.1f} vs {ref['fx']:.1f}) — descolou do ambiente"
            )
            assert dado["fy"] == pytest.approx(ref["fy"], abs=0.5), (
                f"offset {off}: {arquivo} mudou de altura NA FOTO "
                f"({dado['fy']:.1f} vs {ref['fy']:.1f}) — flutuou ou afundou"
            )
            assert dado["fw"] == pytest.approx(ref["fw"], abs=0.5), (
                f"offset {off}: {arquivo} mudou de largura com a panorâmica"
            )
            assert dado["fh"] == pytest.approx(ref["fh"], abs=0.5), (
                f"offset {off}: {arquivo} mudou de altura com a panorâmica"
            )


def test_movel_some_quando_a_classe_nao_carrega_e_volta_quando_carrega(layouts):
    """Sem o layouts.json o ambiente cai na camada procedural — nunca fica vazio."""
    import json as _json
    from PIL import Image as _Image

    dims = {}
    for name, meta in layouts["assets"].items():
        with _Image.open(os.path.join(ASSETS, meta["file"])) as im:
            dims[meta["file"]] = [im.width, im.height]

    script = """
    global.window = global;
    global.document = { createElement: () => ({ getContext: () => null }) };
    require(%(js)s);
    const desenhos = [];
    const grad = { addColorStop() {} };
    const ctx = {
      filter: 'none', globalAlpha: 1,
      save() {}, restore() {}, translate() {}, scale() {}, beginPath() {}, closePath() {},
      arc() {}, ellipse() {}, fill() {}, stroke() {}, fillRect() {}, strokeRect() {},
      moveTo() {}, lineTo() {}, quadraticCurveTo() {}, arcTo() {}, clip() {}, rect() {},
      createLinearGradient: () => grad, createRadialGradient: () => grad,
      measureText: () => ({ width: 100 }), fillText() {},
      drawImage() { desenhos.push('cutout'); },
    };
    // sem layout carregado
    const semLayout = VVStaging.draw(ctx, 1280, 720, { room: 'sala', badge: false });
    const cutoutsSemLayout = desenhos.length;

    // agora com layout + imagens
    const layouts = %(layouts)s;
    const dims = %(dims)s;
    VVStaging._setLayouts(layouts);
    for (const name of Object.keys(layouts.assets)) {
      VVStaging._setImage(layouts.assets[name].file,
        { naturalWidth: dims[layouts.assets[name].file][0],
          naturalHeight: dims[layouts.assets[name].file][1] });
    }
    desenhos.length = 0;
    const comLayout = VVStaging.draw(ctx, 1280, 720, { room: 'sala', badge: false });
    const cutoutsComLayout = desenhos.length;

    // e um ambiente sem layout fotográfico (banheiro) continua procedural
    desenhos.length = 0;
    const banheiro = VVStaging.draw(ctx, 1280, 720, { room: 'banheiro', badge: false });

    console.log(JSON.stringify({
      semLayout: semLayout, cutoutsSemLayout: cutoutsSemLayout,
      comLayout: comLayout, cutoutsComLayout: cutoutsComLayout,
      banheiro: banheiro,
    }));
    """ % {"js": _json.dumps(STAGING_JS), "layouts": _json.dumps(layouts), "dims": _json.dumps(dims)}
    res = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                         cwd=BASE_DIR, timeout=90)
    assert res.returncode == 0, res.stderr
    out = _json.loads(res.stdout.strip().splitlines()[-1])

    # sem layout: desenha (procedural), mas nenhum cutout
    assert out["semLayout"] is True and out["cutoutsSemLayout"] == 0
    # com layout: desenha cutouts de verdade
    assert out["comLayout"] is True
    assert out["cutoutsComLayout"] == len(layouts["rooms"]["sala"]["placements"])
    # banheiro não tem layout fotográfico: cai na procedural
    assert out["banheiro"] is True
