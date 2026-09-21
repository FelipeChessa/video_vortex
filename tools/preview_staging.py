#!/usr/bin/env python3
"""preview_staging.py — confere o layout do staging fotográfico SEM navegador.

O sandbox não tem browser, e o staging fotográfico é justamente aquilo que a
estatística não pega: móvel flutuando, móvel grande demais, dois móveis no mesmo
lugar, quadro abaixo do sofá. Este utilitário reimplementa em PIL a MESMA
matemática de static/js/staging.js (project/cover → frame) e compõe os cutouts
sobre um ambiente sintético, para que a composição possa ser OLHADA.

    python tools/preview_staging.py                 # grade salas × estilos
    python tools/preview_staging.py --tracking      # teste de arrasto (pan/zoom)

Como o layout é lido de static/assets/layouts.json, o que aparece aqui é o que o
navegador vai desenhar. Divergência entre os dois é bug de um dos lados.
"""

from __future__ import annotations

import argparse
import json
import math
import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(BASE_DIR, "static", "assets")
LAYOUTS_PATH = os.path.join(ASSETS, "layouts.json")


# ------------------------------------------------------------------ geometria
def cover_projection(iw: int, ih: int, W: int, H: int, zoom: float, offset_x: float) -> dict:
    """Espelho de VVStaging.coverProjection (mesmo 'cover' do fundo)."""
    base = max(W / iw, H / ih)
    scale = base * zoom
    dw, dh = iw * scale, ih * scale
    max_off = max(0.0, (dw - W) / 2)
    dx = (W - dw) / 2 + max(-max_off, min(max_off, offset_x))
    dy = (H - dh) / 2
    return {"dx": dx, "dy": dy, "scale": scale, "iw": iw, "ih": ih, "W": W, "H": H}


def frame_of(pl: dict, dims: tuple[int, int], proj: dict, anchor: str | None = None) -> dict:
    """Espelho de VVStaging.frameOf. h/bottom/top são frações da ALTURA DA FOTO.

    `anchor` vem dos metadados do ASSET (floor/wall/ceiling/surface) e só é
    consultado quando o placement não define o seu — mesmo comportamento do JS.
    """
    iw, ih, s = proj["iw"], proj["ih"], proj["scale"]
    h = pl.get("h", 0.25) * ih * s
    w = h * (dims[0] / dims[1])
    cx = proj["dx"] + pl["x"] * iw * s
    a = pl.get("anchor") or anchor or "floor"
    if a in ("ceiling", "wall"):
        top = proj["dy"] + pl.get("top", 0.0) * ih * s
    else:
        top = proj["dy"] + pl.get("bottom", 0.85) * ih * s - h
    clamped = False
    H = proj.get("H", 0)
    if H and a not in ("ceiling", "wall") and top + h > H:
        top, clamped = H - h, True
    return {"cx": cx, "top": top, "w": w, "h": h, "bottom": top + h, "clamped": clamped}


# ------------------------------------------------------ filtros CSS → PIL
def apply_filter(img: Image.Image, spec: str, blur_px: float = 0.0) -> Image.Image:
    """Traduz o subconjunto de CSS filter usado pelos estilos para PIL."""
    for token in (spec or "").split(")"):
        token = token.strip().strip(",").strip()
        if not token:
            continue
        try:
            if token.startswith("saturate("):
                img = ImageEnhance.Color(img).enhance(float(token[9:]))
            elif token.startswith("brightness("):
                img = ImageEnhance.Brightness(img).enhance(float(token[11:]))
            elif token.startswith("contrast("):
                img = ImageEnhance.Contrast(img).enhance(float(token[9:]))
            elif token.startswith("sepia("):
                amount = float(token[6:])
                gray = img.convert("L")
                sepia = Image.merge(
                    "RGB",
                    (gray.point(lambda v: min(255, int(v * 1.07))),
                     gray.point(lambda v: min(255, int(v * 0.95))),
                     gray.point(lambda v: min(255, int(v * 0.78)))),
                )
                img = Image.blend(img, sepia, min(1.0, amount))
        except (ValueError, IndexError):
            pass
    if blur_px > 0.2:
        img = img.filter(ImageFilter.GaussianBlur(blur_px))
    return img


def blur_px_for(depth: float) -> float:
    return round((0.5 - depth) * 1.6, 2) if depth < 0.5 else 0.0


# ------------------------------------------------------------ fundo sintético
FLOOR_Y = 0.72  # fração da altura onde fica o encontro parede/piso


def synthetic_room(W: int, H: int, room: str) -> Image.Image:
    """Ambiente vazio plausível (parede + rodapé + piso) para julgar a colagem.

    Não é para ser bonito: é para ter LINHA DE PISO e RODAPÉ — as duas
    referências que dizem se um móvel está plantado no chão ou flutuando. Sem
    elas não há como julgar escala nem alinhamento olhando a imagem.

    Proporções de foto de imóvel: parede ~72%, piso ~28% (câmera alta, grande
    angular), tábuas correndo para a câmera (mais juntas ao fundo).
    """
    outdoor = room in ("varanda", "area")
    wall_top = (196, 207, 214) if outdoor else (214, 208, 197)
    wall_bottom = (219, 226, 230) if outdoor else (236, 231, 222)
    img = Image.new("RGB", (W, H), wall_top)
    d = ImageDraw.Draw(img)

    for y in range(H):
        t = y / max(1, H - 1)
        r = int(wall_top[0] + (wall_bottom[0] - wall_top[0]) * t)
        g = int(wall_top[1] + (wall_bottom[1] - wall_top[1]) * t)
        b = int(wall_top[2] + (wall_bottom[2] - wall_top[2]) * t)
        shade = 1.0 - 0.12 * math.sin(t * math.pi)
        d.line([(0, y), (W, y)], fill=(int(r * shade), int(g * shade), int(b * shade)))

    # janela/luz suave à esquerda, para o ambiente não ficar chapado
    glow = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-W * 0.4, -H * 0.6, W * 0.6, H * 0.9], fill=95)
    img = Image.composite(Image.new("RGB", (W, H), (255, 252, 244)), img,
                          glow.filter(ImageFilter.GaussianBlur(70)))

    floor_y = int(H * FLOOR_Y)
    floor = (150, 146, 138) if outdoor else (152, 121, 92)
    d.rectangle([0, floor_y, W, H], fill=floor)
    # tábuas convergindo (bem simples): mais próximas entre si ao fundo
    for i in range(1, 13):
        t = (i / 13) ** 2.1
        y = floor_y + (H - floor_y) * t
        d.line([(0, y), (W, y)],
               fill=(int(floor[0] * 0.90), int(floor[1] * 0.90), int(floor[2] * 0.90)),
               width=1 + int(t * 2))
    # rodapé: a referência de escala mais útil que existe
    sk = max(3, int(H * 0.028))
    d.rectangle([0, floor_y - sk, W, floor_y], fill=(250, 248, 244))
    d.line([(0, floor_y - sk), (W, floor_y - sk)], fill=(206, 202, 196), width=1)
    return img.filter(ImageFilter.GaussianBlur(0.6))


# ------------------------------------------------------------------ composição
def compose(room: str, style: str, W: int, H: int, layouts: dict,
            zoom: float = 1.22, offset_x: float = 0.0, show_grid: bool = True) -> Image.Image:
    base = synthetic_room(W, H, room)
    room_def = layouts["rooms"].get(room)
    if not room_def or room_def.get("photo") is False:
        return base

    proj = cover_projection(W, H, W, H, zoom, offset_x)  # fundo sintético = foto 1:1
    tint = layouts["styles"].get(style, {})
    placements = sorted(room_def.get("placements", []), key=lambda p: (p.get("depth", 0.7),))
    canvas = base.convert("RGBA")

    for pl in placements:
        meta = layouts["assets"].get(pl["asset"])
        if not meta:
            continue
        path = os.path.join(ASSETS, meta["file"])
        if not os.path.exists(path):
            continue
        cut = Image.open(path).convert("RGBA")
        fr = frame_of(pl, cut.size, proj, meta.get("anchor"))
        if fr["cx"] + fr["w"] / 2 < 0 or fr["cx"] - fr["w"] / 2 > W:
            continue
        w, h = max(1, round(fr["w"])), max(1, round(fr["h"]))

        # sombra de contato (elíptica, difusa), como no contactShadow do JS
        amount = (tint.get("shadow", 0.3)) * max(0.0, min(1.2, 0.35 + pl.get("depth", 0.7) * 0.75))
        if amount > 0.02:
            sh = Image.new("L", (W, H), 0)
            sd = ImageDraw.Draw(sh)
            rx, ry = w * 0.46, max(3, w * 0.075)
            sd.ellipse([fr["cx"] - rx, fr["bottom"] - ry, fr["cx"] + rx, fr["bottom"] + ry],
                       fill=int(108 * amount))
            canvas.alpha_composite(
                Image.merge("RGBA", (
                    Image.new("L", (W, H), 0), Image.new("L", (W, H), 0),
                    Image.new("L", (W, H), 0), sh.filter(ImageFilter.GaussianBlur(max(4, rx * 0.28))),
                ))
            )

        cut = cut.resize((w, h), Image.LANCZOS)
        cut = apply_filter(cut, tint.get("filter", ""), blur_px_for(pl.get("depth", 0.7)))
        if pl.get("flip"):
            cut = cut.transpose(Image.FLIP_LEFT_RIGHT)
        canvas.alpha_composite(cut, (round(fr["cx"] - w / 2), round(fr["top"])))

    if show_grid:
        d = ImageDraw.Draw(canvas)
        d.text((10, 8), f"{room} · {styles_label(layouts, style)}", fill=(255, 255, 255, 230))
        if offset_x:
            d.text((10, H - 22), f"pan {offset_x:+.0f}px", fill=(255, 255, 255, 230))
    return canvas.convert("RGB")


def styles_label(layouts: dict, style: str) -> str:
    return layouts["styles"].get(style, {}).get("label", style)


def contact_sheet(layouts: dict, rooms: list[str], styles: list[str], W: int, H: int, out: str) -> None:
    sheet = Image.new("RGB", (W * len(styles), H * len(rooms)), (18, 18, 22))
    for r, room in enumerate(rooms):
        for c, style in enumerate(styles):
            sheet.paste(compose(room, style, W, H, layouts), (c * W, r * H))
    sheet.save(out, "PNG", optimize=True)
    print(f"{out}  ({sheet.width}x{sheet.height} — {len(rooms)} ambientes × {len(styles)} estilos)")


def compose_tracked(layouts: dict, room: str, style: str, W: int, H: int,
                    photo: Image.Image, zoom: float, offset_x: float) -> Image.Image:
    """Compõe a mobília sobre uma foto JÁ deslocada (como o tour faz de verdade).

    Aqui a projeção é a da foto (que é maior que o canvas), e não a do canvas —
    é justamente o caso em que a mobília desgruda do chão se a conta estiver
    errada.
    """
    iw, ih = photo.size
    canvas = Image.new("RGB", (W, H), (20, 20, 24))
    proj = cover_projection(iw, ih, W, H, zoom, offset_x)
    canvas.paste(photo, (round(proj["dx"]), round(proj["dy"])))

    room_def = layouts["rooms"].get(room) or {}
    tint = layouts["styles"].get(style, {})
    out = canvas.convert("RGBA")
    for pl in sorted(room_def.get("placements", []), key=lambda p: p.get("depth", 0.7)):
        meta = layouts["assets"].get(pl["asset"])
        if not meta:
            continue
        path = os.path.join(ASSETS, meta["file"])
        if not os.path.exists(path):
            continue
        cut = Image.open(path).convert("RGBA")
        fr = frame_of(pl, cut.size, proj, meta.get("anchor"))
        if fr["cx"] + fr["w"] / 2 < 0 or fr["cx"] - fr["w"] / 2 > W:
            continue
        w, h = max(1, round(fr["w"])), max(1, round(fr["h"]))
        cut = apply_filter(cut.resize((w, h), Image.LANCZOS), tint.get("filter", ""),
                           blur_px_for(pl.get("depth", 0.7)))
        if pl.get("flip"):
            cut = cut.transpose(Image.FLIP_LEFT_RIGHT)
        out.alpha_composite(cut, (round(fr["cx"] - w / 2), round(fr["top"])))
    d = ImageDraw.Draw(out)
    d.text((10, 8), f"pan {offset_x:+.0f}px · zoom {zoom:.2f}", fill=(255, 255, 255, 235))
    return out.convert("RGB")


def tracking_strip(layouts: dict, room: str, style: str, W: int, H: int, out: str) -> None:
    """A mobília acompanha a panorâmica? Um quadro por deslocamento.

    A foto de fundo é maior que o canvas (como no tour, que usa 'cover' + zoom),
    então cada quadro mostra a foto cortada e a mobília composta sobre ela.
    """
    zoom = 1.22
    offs = [-0.16, -0.08, 0.0, 0.08, 0.16]
    iw, ih = int(W * zoom * 1.12), int(H * zoom * 1.12)
    photo = synthetic_room(iw, ih, room)

    sheet = Image.new("RGB", (W * len(offs), H), (18, 18, 22))
    for i, frac in enumerate(offs):
        proj = cover_projection(iw, ih, W, H, zoom, 0)
        max_off = max(0.0, (proj["iw"] * proj["scale"] - W) / 2)
        sheet.paste(
            compose_tracked(layouts, room, style, W, H, photo, zoom, frac * W * 0.5 + max_off * 0),
            (i * W, 0),
        )
    sheet.save(out, "PNG", optimize=True)
    print(f"{out}  (arrasto: {len(offs)} deslocamentos de panorâmica — móveis devem ficar fixos no piso)")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rooms", default="sala,quarto,cozinha,escritorio,varanda")
    ap.add_argument("--styles", default="moderno,minimalista,rustico,luxo")
    ap.add_argument("--size", default="640x480", help="tamanho de cada célula (foto 4:3)")
    ap.add_argument("--out", default=os.path.join(ASSETS, "_staging_preview.png"))
    ap.add_argument("--tracking", action="store_true", help="gera também a tira de arrasto")
    args = ap.parse_args(argv)

    with open(LAYOUTS_PATH, encoding="utf-8") as fh:
        layouts = json.load(fh)

    W, H = (int(v) for v in args.size.lower().split("x"))
    rooms = [r.strip() for r in args.rooms.split(",") if r.strip()]
    styles = [s.strip() for s in args.styles.split(",") if s.strip()]

    contact_sheet(layouts, rooms, styles, W, H, args.out)
    if args.tracking:
        tracking_strip(layouts, rooms[0], styles[0], W, H,
                       os.path.join(ASSETS, "_staging_tracking.png"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
