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
              ├─ 5. [opcional] suprime sombra projetada no chão
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
    --kill-shadows  # derruba sombra de chão (cinza claro, baixa saturação)
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
    # a foto veio com sombra projetada no chão, que aparecia como borrão cinza
    "vase-decor": {"kill_shadows": True},
    # quadro tem passe-partout branco cercado pela moldura: não pode furar
    "wall-art": {"fill_holes": True},
    # lâmpada de mesa clara: derrubar sombra comeria a borda da cúpula,
    # então NÃO ativa kill_shadows aqui (fica no padrão)
    "table-lamp": {},
}


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


def suppress_shadows(
    alpha: np.ndarray, arr: np.ndarray, bg: np.ndarray, saturation: float = 26.0, keep: float = 0.94
) -> np.ndarray:
    """Derruba sombra projetada: acromática, clara e com alpha parcial.

    O teste é conservador de propósito — só age em pixel *sem cor*, *mais claro
    que o objeto* e que **não** chegou a alpha cheio. Objeto colorido (madeira,
    terracota) tem croma alto e nunca é atingido; objeto escuro (moldura preta)
    falha no teste de claridade. Borda antialiasada do objeto também é poupada
    porque herda o croma do objeto.
    """
    chroma = arr.max(axis=2) - arr.min(axis=2)
    luma = arr.mean(axis=2)
    bg_luma = float(bg.mean())

    achromatic = chroma < saturation
    light = luma > (bg_luma - 46.0)
    partial = alpha < 0.92

    kill = achromatic & light & partial
    return np.where(kill, alpha * (1.0 - keep), alpha)


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
) -> dict:
    im = Image.open(src).convert("RGB")
    arr = np.asarray(im).astype(np.float32)

    bg = np.array(bg_color, dtype=np.float32) if bg_color else estimate_bg(arr)

    alpha = key_out(arr, low, high, bg)
    alpha = despeckle(alpha)
    if kill_shadows:
        alpha = suppress_shadows(alpha, arr, bg)
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
    }


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
        )
        done.append((name, os.path.join(args.out_dir, f"{name}.png")))
        print(
            f"{info['src']:<16} {info['size']:<11} {str(info['bg']):<15} "
            f"{info['coverage']:>6.1f}%  {info['steps'] or 'padrão'}  ({info['kb']}K)"
        )

    if args.preview:
        prev = os.path.join(args.out_dir, "_preview.png")
        make_preview(done, prev)
        print(f"\ncontact sheet: {prev}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
