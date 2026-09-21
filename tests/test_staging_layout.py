"""Validação do layout do staging fotográfico (static/assets/layouts.json).

O layout é a fonte única de verdade do staging fotográfico: o navegador
(static/js/staging.js) e o conferidor offline (tools/preview_staging.py) leem o
mesmo arquivo. Um erro aqui aparece como móvel flutuando, cortado na borda ou
sumido — e nenhum desses casos é pego pelos testes de API.
"""

import json
import os

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(BASE_DIR, "static", "assets")
LAYOUTS_PATH = os.path.join(ASSETS, "layouts.json")

# Medido: com o zoom do tour (1.22) o objeto sai do quadro quando
# bottom * zoom > 1 para a foto mais larga que o canvas (16:9 → 0.82).
# 0.90 é o último valor que sobra margem em qualquer aspecto.
BOTTOM_LIMIT = 0.90
STYLE_KEYS = ["moderno", "minimalista", "rustico", "luxo"]


@pytest.fixture(scope="module")
def layouts():
    with open(LAYOUTS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _placements(layouts):
    for room, room_def in layouts["rooms"].items():
        for pl in room_def.get("placements", []):
            yield room, pl


# ------------------------------------------------------------------ estrutura
def test_layout_tem_os_quatro_estilos(layouts):
    assert set(layouts["styles"]) == set(STYLE_KEYS)
    for key, style in layouts["styles"].items():
        assert style.get("filter"), f"estilo {key} sem filtro"
        assert 0 < style.get("shadow", 0) <= 1, f"estilo {key} com sombra fora de 0..1"


def test_todo_asset_do_layout_existe_em_disco(layouts):
    for name, meta in layouts["assets"].items():
        path = os.path.join(ASSETS, meta["file"])
        assert os.path.exists(path), f"asset {name} aponta para arquivo inexistente: {meta['file']}"
        assert meta.get("anchor") in ("floor", "wall", "ceiling", "surface"), (
            f"asset {name} com anchor inválido: {meta.get('anchor')}"
        )


def test_ambientes_fotograficos_tem_mobilia(layouts):
    for room, room_def in layouts["rooms"].items():
        if room_def.get("photo") is False:
            assert not room_def.get("placements"), (
                f"{room} está marcado como não-fotográfico mas tem placements"
            )
            continue
        assert room_def.get("placements"), f"{room} é fotográfico mas está vazio"


def test_rooms_do_layout_cobrem_o_detectroom(layouts):
    """Todo ambiente que VVScript.detectRoom devolve precisa existir no layout.

    Sem isso, um ambiente novo cai silenciosamente no fallback procedural.
    """
    js = open(os.path.join(BASE_DIR, "static", "js", "scriptgen.js"), encoding="utf-8").read()
    esperados = set()
    for linha in js.splitlines():
        if "return \"" in linha and ("/sala/" in linha or "return" in linha):
            pass
    # extrai só os returns de detectRoom
    dentro = False
    for linha in js.splitlines():
        if "function detectRoom" in linha:
            dentro = True
        if dentro and "return" in linha:
            parte = linha.split('return "')[1] if 'return "' in linha else None
            if parte:
                esperados.add(parte.split('"')[0])
        if dentro and linha.strip() == "}":
            break
    assert esperados, "não consegui extrair os ambientes de detectRoom"
    faltando = esperados - set(layouts["rooms"])
    assert not faltando, f"ambientes sem layout fotográfico: {sorted(faltando)}"


# ------------------------------------------------------------------ geometria
def test_placement_referencia_asset_conhecido(layouts):
    for room, pl in _placements(layouts):
        assert pl["asset"] in layouts["assets"], f"{room}: asset desconhecido {pl['asset']}"


def test_coordenadas_nos_limites(layouts):
    for room, pl in _placements(layouts):
        anchor = pl.get("anchor") or layouts["assets"][pl["asset"]].get("anchor", "floor")
        ctx = f"{room}/{pl['asset']}"

        if "x" in pl:
            assert 0.0 <= pl["x"] <= 1.0, f"{ctx}: x fora de 0..1 ({pl['x']})"

        assert 0 < pl["h"] <= 0.6, f"{ctx}: h fora de 0.05..0.6 ({pl['h']})"

        if anchor in ("ceiling", "wall"):
            assert "top" in pl, f"{ctx}: ancorado no alto precisa de top"
            assert 0.0 <= pl["top"] <= 0.6, f"{ctx}: top fora de 0..0.6 ({pl['top']})"
        else:
            assert "bottom" in pl, f"{ctx}: ancorado no chão precisa de bottom"
            assert pl["bottom"] <= BOTTOM_LIMIT, (
                f"{ctx}: bottom {pl['bottom']} passa do limite {BOTTOM_LIMIT} — "
                "o objeto é cortado na borda inferior com o zoom do tour"
            )


def test_profundidade_valida_e_ordenavel(layouts):
    for room, pl in _placements(layouts):
        depth = pl.get("depth", 0.7)
        assert 0.0 <= depth <= 1.0, f"{room}/{pl['asset']}: depth fora de 0..1"


def test_objetos_de_parede_nao_ficam_no_chao(layouts):
    """O anchor mora no ASSET: quadro/luminária pendente não podem ser 'floor'.

    (Este teste existe porque esse merge já faltou uma vez: o quadro era
    desenhado no chão e ficava escondido atrás do sofá.)
    """
    for room, pl in _placements(layouts):
        meta = layouts["assets"][pl["asset"]]
        esperado = {"wall-art": "wall", "pendant": "ceiling", "table-lamp": "surface"}
        if pl["asset"] in esperado:
            assert meta.get("anchor") == esperado[pl["asset"]], (
                f"{pl['asset']} deveria ser '{esperado[pl['asset']]}'"
            )
            assert "bottom" not in pl or meta["anchor"] in ("surface", "floor"), (
                f"{room}/{pl['asset']}: objeto de parede/teto não usa bottom"
            )


def test_movel_de_apoio_desenha_depois_do_que_o_sustenta(layouts):
    """A luminária de mesa precisa ser desenhada DEPOIS do móvel que a sustenta.

    O depth decide a ordem (menor = mais ao fundo = desenhado antes). Se a
    luminária tivesse depth menor que a mesinha, ela ficaria atrás e sumiria —
    é o modo de falha que este teste trava. O par intencionalmente dividido
    (mesinha 0.45 / luminária 0.50, mesma coordenada) é o caso correto.
    """
    SUPPORT = {"surface"}

    for room, room_def in layouts["rooms"].items():
        pls = room_def.get("placements", [])
        for i, apoio in enumerate(pls):
            anchor = layouts["assets"][apoio["asset"]].get("anchor")
            if anchor not in SUPPORT:
                continue
            # procura o móvel logo abaixo, na mesma coordenada
            hospedes = [
                p for j, p in enumerate(pls)
                if j != i
                and layouts["assets"][p["asset"]].get("anchor") not in SUPPORT
                and abs(p.get("x", 0) - apoio.get("x", 0)) <= 0.08
                and p.get("bottom", 1) <= apoio.get("bottom", 1) + 0.30
            ]
            assert hospedes, (
                f"{room}: {apoio['asset']} em x={apoio.get('x')} não tem móvel de apoio "
                "sob ele — a luminária ficaria no ar"
            )
            hospede = min(hospedes, key=lambda p: abs(p.get("bottom", 0) - apoio.get("bottom", 0)))
            assert apoio.get("depth", 0.7) > hospede.get("depth", 0.7), (
                f"{room}: {apoio['asset']} (depth {apoio.get('depth')}) precisa de depth "
                f"maior que {hospede['asset']} (depth {hospede.get('depth')}) para ser "
                "desenhado por cima do móvel que o sustenta"
            )


def test_mobilia_cabe_na_largura_da_foto(layouts):
    """Nenhum móvel sozinho pode ocupar mais que a largura inteira da foto."""
    from PIL import Image

    for room, pl in _placements(layouts):
        path = os.path.join(ASSETS, layouts["assets"][pl["asset"]]["file"])
        with Image.open(path) as im:
            aspecto = im.width / im.height
        largura = pl["h"] * aspecto  # fração da largura da foto
        assert largura <= 1.0, f"{room}/{pl['asset']}: ocupa {largura:.2f} da largura da foto"
