#!/usr/bin/env python3
"""make_assets.py — recorta móveis fotografados em fundo branco puro para PNG com alpha.

O staging fotográfico do VideoVortex compõe *cutouts* fotográficos dentro do
panorama 360°. Esses cutouts precisam de alfa limpo (sem franja branca, sem halo)
para que a composição não denuncie o recorte.

Pipeline:

    static/assets/raw/<nome>.png   (foto em fundo branco puro)
              │
              ├─ 1. estima a cor do fundo pela moldura da imagem (mediana)
              ├─ 2. mede o desvio de cada pixel em relação ao fundo
              ├─ 3. converte esse desvio em alpha com rampa suave (antialias)
              ├─ 4. suprime ilhas soltas (respingo de compressão)
              ├─ 5. [opcional] suprime sombra projetada no chão (faixa de baixo
              │                 + croma neutro + clara: ver suppress_shadows)
              ├─ 6. [opcional] preenche buracos fechados (ex.: passe-partout do quadro)
              ├─ 7. desfaz o *spill* branco das bordas (un-premultiply)
              ├─ 8. recorta no bounding box, limitando o maior lado
              └─ 9. salva com margem uniforme
              ▼
    static/assets/<nome>.png       (cutout RGBA pronto para compor)

Uso
---
    python tools/make_assets.py                  # processa todos os raw/*.png
    python tools/make_assets.py --only vase-decor
    python tools/make_assets.py --preview        # + contact sheet de conferência
    python tools/make_assets.py --bg-color 255,0,255   # fundo diferente do branco

Ajuste fino (quando um asset sai com buraco, franja ou sombra sobrando):

    --low   0.045   # desvio abaixo disso = 100% transparente
    --high  0.150   # desvio acima disso = 100% opaco
    --kill-shadows  # derruba sombra de chão (neutra, clara, faixa de baixo)
    --shadow-band 0.22 --shadow-tol 80   # ajuste fino dessa sombra
    --fill-holes    # torna opaco o que está cercado pelo objeto

Dois detalhes que só aparecem na prática:

* **Sombra projetada** vem junto na foto e, se ficar, o cutout carrega um borrão
  cinza que denuncia a colagem sobre madeira/parede. O sinal dela é pequeno
  (pouco desvio do fundo) e acromático, então dá para derrubá-la sem tocar no
  objeto — desde que o objeto tenha cor. Ative por asset.
* **Buraco interno** (o passe-partout branco de um quadro, por exemplo) fica
  transparente e o ambiente aparece através dele. `--fill-holes` resolve.

Dependências: Pillow + NumPy (scipy é opcional, só acelera/qualifica).
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "static", "assets", "raw")
OUT_DIR = os.path.join(BASE_DIR, "static", "assets")

# Ajuste por asset. Só entram aqui os que realmente precisam — o padrão cobre a
# maioria dos casos. Nome = nome do arquivo sem extensão.
PRESETS: dict[str, dict] = {
    # Band/tol medidos olhando o resultado sobre fundo escuro (o fundo claro
    # esconde exatamente o defeito que se quer ver). Cada linha abaixo tinha
    # sombra projetada visível na foto original.
    "sofa": {"kill_shadows": True, "shadow_band": 0.22, "shadow_tol": 80.0},
    "bed": {"kill_shadows": True, "shadow_band": 0.18, "shadow_tol": 30.0},
    "vase-decor": {"kill_shadows": True, "shadow_band": 0.25, "shadow_tol": 40.0},
    "table-lamp": {"kill_shadows": True, "shadow_band": 0.12, "shadow_tol": 30.0},
    "dining-set": {"kill_shadows": True, "shadow_band": 0.12, "shadow_tol": 30.0},
    "nightstand": {"kill_shadows": True, "shadow_band": 0.12, "shadow_tol": 30.0},
    "plant": {"kill_shadows": True, "shadow_band": 0.10, "shadow_tol": 28.0},
    # quadro tem passe-partout branco cercado pela moldura: não pode furar
    "wall-art": {"fill_holes": True},
    # poltrona bouclé clara: os pés claros moram na faixa de chão; o croma da
    # lã e o teste de faixa seguram, mas a margem é pequena — fica no padrão
    # (sem kill_shadows) para não arriscar comer o móvel.
    "armchair": {},
}

SHADOW_LOSS_WARN = 0.08


# --------------------------------------------------------------------- núcleo
def estimate_bg(arr: np.ndarray, border: float = 0.06) -> np.ndarray:
    """Cor do fundo = mediana da moldura da imagem (ignora o objeto no centro).

    Mediana (e não média) protege contra canto com gradiente ou sombra.
    """
    h, w = arr.shape[:2]
    bh, bw = max(1, int(h * border)), max(1, int(w * border))
    ring = np.concatenate(
        [
            arr[:bh, :, :].reshape(-1, 3),
            arr[-bh:, :, :].reshape(-1, 3),
            arr[:, :bw, :].reshape(-1, 3),
            arr[:, -bw:, :].reshape(-1, 3),
        ]
    )
    return np.median(ring, axis=0)


def smoothstep(edge0: float, edge1: float, x: np.ndarray) -> np.ndarray:
    """Rampa suave (Hermite) — borda antialiasada em vez de serrilhada."""
    if edge1 <= edge0:
        edge1 = edge0 + 1e-6
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def key_out(arr: np.ndarray, low: float, high: float, bg: np.ndarray) -> np.ndarray:
    """Alpha (0..1) de cada pixel a partir do desvio em relação ao fundo."""
    # desvio = maior diferença absoluta em qualquer canal, normalizada
    diff = np.abs(arr - bg.reshape(1, 1, 3)).max(axis=2) / 255.0

    # luminância também conta: fundo é claro, então objeto escuro salta mesmo
    # quando um dos canais coincide com o fundo (cinza sobre cinza, p.ex.)
    luma = arr.mean(axis=2) / 255.0
    bg_luma = float(bg.mean() / 255.0)
    dark = np.clip(bg_luma - luma, 0.0, 1.0)

    signal = np.maximum(diff, dark * 0.85)
    return smoothstep(low, high, signal)


def floor_band(arr: np.ndarray, alpha: np.ndarray, band: float) -> np.ndarray:
    """Máscara da faixa de baixo do OBJETO (não da imagem).

    Delimitar pela bounding box do objeto — e não pela altura da imagem — é o que
    impede que um vaso baixo ou uma mesa pequena virem "faixa de chão" inteira.
    """
    ys, _ = np.where(alpha > 0.35)
    if not len(ys):
        return np.zeros_like(alpha, dtype=bool)
    y0, y1 = int(ys.min()), int(ys.max())
    top = int(y1 - band * max(1, y1 - y0))
    mask = np.zeros_like(alpha, dtype=bool)
    mask[top:, :] = True
    return mask


def suppress_shadows(
    alpha: np.ndarray,
    arr: np.ndarray,
    bg: np.ndarray,
    band: float = 0.20,
    saturation: float = 8.0,
    luma_tol: float = 35.0,
) -> np.ndarray:
    """Derruba a sombra projetada no chão, deixando o móvel intacto.

    A sombra de uma foto de produto é inconfundível quando medida: **neutra**
    (croma ~1, contra 26 no corpo do sofá, 53 na cúpula da luminária, 106 no
    vaso) e **clara** (luma 190–236, contra 164 no corpo do sofá). E, claro,
    fica na **faixa de baixo** do objeto.

    Somados, os três testes são seguros justamente nos dois casos que quebravam
    a abordagem ingênua ("alfa parcial + cor clara"):

      * **edredom branco de cama** — claro e neutro, mas *não* está na faixa de
        chão (é o meio do objeto), então o teste de faixa poupa;
      * **corpo e braços do sofá** — estão na faixa de baixo, mas têm croma 26
        (tecido bege), então o teste de croma poupa.

    O que sobra de luz no que foi removido é reposto pela sombra de contato do
    staging (ver `contactShadow` em static/js/staging.js).

    Parâmetros por asset (ver PRESETS):
      band    — fração da altura do objeto que conta como "perto do chão"
      luma_tol — distância até a cor do fundo que ainda conta como sombra
      saturation — croma abaixo disso é "neutro"
    """
    luma = arr.mean(axis=2)
    chroma = arr.max(axis=2) - arr.min(axis=2)

    kill = (
        floor_band(arr, alpha, band)
        & (chroma < saturation)
        & (luma > (bg.mean() - luma_tol))
    )
    return np.where(kill, 0.0, alpha)


def _label_outside(mask_free: np.ndarray) -> np.ndarray:
    """True onde a região livre está conectada à borda da imagem (é 'fora')."""
    try:
        from scipy import ndimage  # type: ignore

        labeled, _ = ndimage.label(mask_free)
        border_labels = np.unique(
            np.concatenate([labeled[0, :], labeled[-1, :], labeled[:, 0], labeled[:, -1]])
        )
        border_labels = border_labels[border_labels != 0]
        return np.isin(labeled, border_labels)
    except Exception:
        # fallback sem scipy: propaga a partir da borda por dilatação
        outside = np.zeros_like(mask_free)
        outside[0, :] = mask_free[0, :]
        outside[-1, :] = mask_free[-1, :]
        outside[:, 0] = mask_free[:, 0]
        outside[:, -1] = mask_free[:, -1]
        for _ in range(max(mask_free.shape)):
            new = outside.copy()
            new[1:, :] |= outside[:-1, :]
            new[:-1, :] |= outside[1:, :]
            new[:, 1:] |= outside[:, :-1]
            new[:, :-1] |= outside[:, 1:]
            new &= mask_free
            if np.array_equal(new, outside):
                break
            outside = new
        return outside


def fill_holes(alpha: np.ndarray, thresh: float = 0.35) -> np.ndarray:
    """Torna opaco o que está cercado pelo objeto (buraco fechado)."""
    free = alpha <= thresh
    if not free.any():
        return alpha
    holes = free & ~_label_outside(free)
    return np.where(holes, 1.0, alpha)


def despeckle(alpha: np.ndarray, min_frac: float = 0.002) -> np.ndarray:
    """Zera ilhas de alpha muito pequenas (respingo de compressão no fundo)."""
    solid = alpha > 0.35
    if not solid.any():
        return alpha
    try:
        from scipy import ndimage  # type: ignore

        labeled, n = ndimage.label(solid)
        if n <= 1:
            return alpha
        idx = np.arange(1, n + 1)
        sizes = ndimage.sum(np.ones_like(labeled), labeled, idx)
        keep = idx[(sizes / float(alpha.size)) >= min_frac]
        return np.where(np.isin(labeled, keep) | (labeled == 0), alpha, 0.0)
    except Exception:
        return np.where(alpha < 0.06, 0.0, alpha)


def unpremultiply_white(rgb: np.ndarray, alpha: np.ndarray) -> np.ndarray:
    """Remove o *spill* branco das bordas semitransparentes.

    Um pixel de borda é mistura física objeto+fundo. Para recompor sobre outro
    fundo sem franja clara, recupera-se a cor do objeto:

        c_obj = (c_pixel - (1 - a) * branco) / a
    """
    a = np.clip(alpha, 1e-3, 1.0)[..., None]
    return np.clip((rgb - (1.0 - a) * 255.0) / a, 0.0, 255.0)


def crop_to_content(img: Image.Image, margin_frac: float = 0.02) -> Image.Image:
    """Recorta no conteúdo visível e devolve margem uniforme."""
    bbox = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if bbox is None:
        return img
    pad = int(max(img.size) * margin_frac)
    return img.crop(
        (
            max(0, bbox[0] - pad),
            max(0, bbox[1] - pad),
            min(img.width, bbox[2] + pad),
            min(img.height, bbox[3] + pad),
        )
    )


def process_one(
    src: str,
    dst: str,
    low: float,
    high: float,
    bg_color: tuple[int, int, int] | None = None,
    max_side: int = 1400,
    kill_shadows: bool = False,
    do_fill_holes: bool = False,
    shadow_tol: float = 35.0,
    shadow_band: float = 0.20,
) -> dict:
    im = Image.open(src).convert("RGB")
    arr = np.asarray(im).astype(np.float32)

    bg = np.array(bg_color, dtype=np.float32) if bg_color else estimate_bg(arr)

    alpha = key_out(arr, low, high, bg)
    alpha = despeckle(alpha)
    warn = ""
    if kill_shadows:
        before = float(alpha.sum())
        alpha = suppress_shadows(alpha, arr, bg, band=shadow_band, luma_tol=shadow_tol)
        if before > 0:
            lost = 1.0 - float(alpha.sum()) / before
            if lost > SHADOW_LOSS_WARN:
                warn = f"  ⚠ supressão de sombra removeu {lost:.1%} do alpha — revise"
    if do_fill_holes:
        alpha = fill_holes(alpha)

    # un-premultiply DEPOIS de todo ajuste de alpha: usa o alpha final
    rgb = unpremultiply_white(arr, alpha)

    img = crop_to_content(Image.fromarray(np.dstack([rgb, alpha * 255.0]).astype(np.uint8), "RGBA"))

    # cutout de móvel não precisa de 4K e o panorama desenha vários por quadro
    if max(img.size) > max_side:
        scale = max_side / max(img.size)
        img = img.resize(
            (max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS
        )

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    img.save(dst, "PNG", optimize=True)

    return {
        "src": os.path.basename(src),
        "size": f"{img.width}x{img.height}",
        "coverage": float((alpha > 0.5).mean() * 100.0),
        "bg": tuple(int(v) for v in bg),
        "kb": os.path.getsize(dst) // 1024,
        "steps": ("shadow " if kill_shadows else "") + ("holes" if do_fill_holes else ""),
        "warn": warn,
    }


def shadow_loss(arr: np.ndarray, low: float, high: float, bg: np.ndarray,
                band: float = 0.20, luma_tol: float = 35.0) -> float:
    """Fração da massa de alpha que a supressão de sombra removeria.

    Serve para decidir (e para travar em teste) se um asset aguenta ou não a
    supressão: acima de ~8% o que está sumindo é o objeto, não a sombra.
    """
    alpha = despeckle(key_out(arr, low, high, bg))
    before = float(alpha.sum())
    if before <= 0:
        return 0.0
    return 1.0 - float(suppress_shadows(alpha, arr, bg, band=band, luma_tol=luma_tol).sum()) / before


# ------------------------------------------------------------------ conferência
def make_preview(items: list[tuple[str, str]], out_path: str, cell: int = 240) -> None:
    """Contact sheet: cada cutout sobre 3 fundos.

    Os fundos são de propósito **médio, quente e escuro** — nada de branco.
    Fundo branco esconde exatamente o defeito que se quer enxergar (franja
    clara/halo). Sobre o fundo escuro, halo branco aparece na hora.
    """
    bgs = [(126, 126, 130), (104, 74, 48), (26, 28, 32)]
    cols, rows = len(bgs), max(1, len(items))
    sheet = Image.new("RGB", (cell * cols, cell * rows), (16, 16, 18))

    for row, (_name, path) in enumerate(items):
        cut = Image.open(path).convert("RGBA")
        scale = min((cell - 20) / cut.width, (cell - 20) / cut.height)
        cut = cut.resize(
            (max(1, round(cut.width * scale)), max(1, round(cut.height * scale))), Image.LANCZOS
        )
        for col, bg in enumerate(bgs):
            tile = Image.new("RGB", (cell, cell), bg)
            tile.paste(cut, ((cell - cut.width) // 2, (cell - cut.height) // 2), cut)
            sheet.paste(tile, (col * cell, row * cell))

    sheet.save(out_path, "PNG", optimize=True)


# ------------------------------------------------------------------------ CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw-dir", default=RAW_DIR)
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--only", default=None, help="processa só um asset (nome sem extensão)")
    ap.add_argument("--low", type=float, default=0.045, help="desvio de alpha 0")
    ap.add_argument("--high", type=float, default=0.150, help="desvio de alpha 1")
    ap.add_argument("--max-side", type=int, default=1400, help="maior lado do cutout final")
    ap.add_argument("--bg-color", default=None, help="fundo fixo 'r,g,b' em vez de estimado")
    ap.add_argument("--kill-shadows", action="store_true", help="força em todos os assets")
    ap.add_argument("--fill-holes", action="store_true", help="força em todos os assets")
    ap.add_argument("--shadow-tol", type=float, default=None,
                    help="força a tolerância de luminância da sombra (padrão 35)")
    ap.add_argument("--shadow-band", type=float, default=None,
                    help="força a faixa de chão do objeto (0..1, padrão 0.20)")
    ap.add_argument("--no-presets", action="store_true", help="ignora a tabela PRESETS")
    ap.add_argument("--preview", action="store_true", help="gera contact sheet de conferência")
    args = ap.parse_args(argv)

    bg_color = None
    if args.bg_color:
        parts = tuple(int(v) for v in args.bg_color.split(","))
        if len(parts) != 3:
            ap.error("--bg-color espera 'r,g,b'")
        bg_color = parts

    sources = sorted(glob.glob(os.path.join(args.raw_dir, "*.png")))
    if args.only:
        sources = [s for s in sources if os.path.splitext(os.path.basename(s))[0] == args.only]
    if not sources:
        print(f"nenhum PNG em {args.raw_dir}", file=sys.stderr)
        return 1

    done: list[tuple[str, str]] = []
    print(f"{'asset':<16} {'saída':<11} {'fundo':<15} {'área':>7}  {'ajustes'}")
    print("-" * 64)
    for src in sources:
        name = os.path.splitext(os.path.basename(src))[0]
        preset = {} if args.no_presets else PRESETS.get(name, {})
        info = process_one(
            src,
            os.path.join(args.out_dir, f"{name}.png"),
            args.low,
            args.high,
            bg_color,
            args.max_side,
            kill_shadows=preset.get("kill_shadows", False) or args.kill_shadows,
            do_fill_holes=preset.get("fill_holes", False) or args.fill_holes,
            shadow_tol=args.shadow_tol if args.shadow_tol is not None
            else preset.get("shadow_tol", 35.0),
            shadow_band=args.shadow_band if args.shadow_band is not None
            else preset.get("shadow_band", 0.20),
        )
        done.append((name, os.path.join(args.out_dir, f"{name}.png")))
        print(
            f"{info['src']:<16} {info['size']:<11} {str(info['bg']):<15} "
            f"{info['coverage']:>6.1f}%  {info['steps'] or 'padrão'}  ({info['kb']}K)"
            f"{info['warn']}"
        )

    if args.preview:
        prev = os.path.join(args.out_dir, "_preview.png")
        make_preview(done, prev)
        print(f"\ncontact sheet: {prev}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
