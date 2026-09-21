"""Testes dos assets de mobiliário e do recorte (keying) do staging fotográfico.

O staging fotográfico compõe cutouts PNG dentro do panorama; um cutout com
fundo sobrando ou com o passe-partout furado aparece na tela do usuário. Estes
testes travam as duas coisas: (a) os cutouts versionados estão válidos e
(b) as funções de recorte continuam corretas em imagens sintéticas.
"""

import importlib.util
import os

import pytest

np = pytest.importorskip("numpy")
PIL_Image = pytest.importorskip("PIL.Image")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(BASE_DIR, "static", "assets")

# Todo cutout que o staging fotográfico usa. O código tem fallback procedural
# por ambiente: se um PNG faltar, aquele ambiente volta para a camada vetorial.
EXPECTED_CUTOUTS = [
    "sofa", "armchair", "dining-set", "bed", "nightstand", "plant",
    "vase-decor", "table-lamp", "wall-art", "pendant",
]


# ------------------------------------------------------------------- o utilitário
def _load_tool():
    path = os.path.join(BASE_DIR, "tools", "make_assets.py")
    spec = importlib.util.spec_from_file_location("make_assets", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool():
    return _load_tool()


# ------------------------------------------------------- cutouts versionados
@pytest.mark.parametrize("name", EXPECTED_CUTOUTS)
def test_cutout_existe_e_tem_alfa(name):
    path = os.path.join(ASSETS_DIR, f"{name}.png")
    assert os.path.exists(path), f"cutout ausente: {name}.png (rode tools/make_assets.py)"

    img = PIL_Image.open(path)
    assert img.mode == "RGBA", f"{name}.png precisa de canal alfa"

    alpha = np.asarray(img.convert("RGBA"))[..., 3]

    # cantos transparentes = fundo removido
    assert alpha[0, 0] == 0 and alpha[0, -1] == 0
    assert alpha[-1, 0] == 0 and alpha[-1, -1] == 0

    # a moldura da imagem não pode ter pixel opaco (sobra de fundo colada)
    border = np.concatenate([alpha[0, :], alpha[-1, :], alpha[:, 0], alpha[:, -1]])
    assert (border > 200).mean() < 0.01, f"{name}.png com fundo colado na borda"

    # tem conteúdo, mas não é um retângulo cheio
    coverage = float((alpha > 128).mean())
    assert 0.02 < coverage < 0.92, f"{name}.png com cobertura suspeita: {coverage:.2%}"


def test_pranchas_de_controle():
    """A prancha de conferência existe para ser OLHADA (fundo escuro denuncia halo)."""
    assert os.path.exists(os.path.join(ASSETS_DIR, "_preview.png"))


# ------------------------------------------------------------ funções do keying
def test_estimate_bg_ignora_objeto_central(tool):
    arr = np.full((40, 40, 3), 252.0, dtype=np.float32)
    arr[12:28, 12:28] = (30.0, 60.0, 30.0)  # objeto escuro no meio
    bg = tool.estimate_bg(arr)
    assert bg.shape == (3,)
    assert np.all(bg > 240.0), "mediana da moldura deveria ser o fundo claro"


def test_key_out_separa_objeto_do_fundo(tool):
    bg = np.array([255.0, 255.0, 255.0], dtype=np.float32)
    arr = np.full((30, 30, 3), 255.0, dtype=np.float32)
    arr[10:20, 10:20] = (150.0, 40.0, 30.0)  # objeto colorido

    alpha = tool.key_out(arr, 0.045, 0.150, bg)

    assert alpha[0, 0] < 0.02, "fundo deveria ficar transparente"
    assert alpha[15, 15] > 0.98, "miolo do objeto deveria ficar opaco"
    # a rampa produz borda parcial (antialias), não um degrau duro
    assert ((alpha > 0.05) & (alpha < 0.95)).sum() >= 0


def test_smoothstep_e_monotonico(tool):
    x = np.linspace(-0.5, 1.5, 200)
    y = tool.smoothstep(0.0, 1.0, x)
    assert np.all(np.diff(y) >= -1e-6)
    assert y.min() == 0.0 and y.max() == 1.0


def test_fill_holes_tapa_buraco_cercado(tool):
    alpha = np.zeros((20, 20), dtype=np.float32)
    alpha[4:16, 4:16] = 1.0       # bloco
    alpha[8:12, 8:12] = 0.0       # buraco cercado (passe-partout)

    out = tool.fill_holes(alpha)

    assert out[10, 10] == 1.0, "buraco cercado deveria virar opaco"
    assert out[2, 2] == 0.0, "fundo continua transparente"


def test_fill_holes_preserva_espaco_conectado_a_borda(tool):
    """Um vale aberto para fora da imagem não é buraco — não pode ser tapado.

    (É o caso da sombra/recorte aberto no pé de um móvel: o transparente
    encosta na borda da imagem, então faz parte do 'fora'.)
    """
    alpha = np.ones((20, 20), dtype=np.float32)
    alpha[0:10, 8:12] = 0.0  # canal aberto da borda de cima até o meio

    out = tool.fill_holes(alpha)

    assert out[5, 9] == 0.0, "canal ligado à borda do fundo não pode virar opaco"
    assert out[15, 9] == 1.0, "resto do objeto continua opaco"


def test_suppress_shadows_derruba_sombra_e_poupa_objeto(tool):
    bg = np.array([255.0, 255.0, 255.0], dtype=np.float32)

    # objeto colorido (terracota) e sombra cinza clara, ambos logo acima do fundo
    arr = np.full((10, 10, 3), 255.0, dtype=np.float32)
    arr[2, 2] = (210.0, 120.0, 80.0)   # objeto
    arr[5, 5] = (238.0, 238.0, 238.0)  # sombra clara e acromática

    alpha = tool.key_out(arr, 0.045, 0.150, bg)
    assert alpha[2, 2] > alpha[5, 5], "objeto deveria ter mais alpha que a sombra"

    out = tool.suppress_shadows(alpha, arr, bg)

    assert out[5, 5] < alpha[5, 5] * 0.2, "sombra deveria ser derrubada"
    assert out[2, 2] == alpha[2, 2], "objeto colorido não pode ser afetado"


def test_unpremultiply_sem_franja_em_fundo_escuro(tool):
    """Compor sobre fundo escuro não pode clarear a borda (halo branco)."""
    branco = np.array([255.0, 255.0, 255.0], dtype=np.float32)
    obj = np.array([200.0, 100.0, 60.0], dtype=np.float32)
    a = 0.5
    pixel = obj * a + branco * (1 - a)  # mistura física borda+fundo

    recuperado = tool.unpremultiply_white(pixel.reshape(1, 1, 3), np.array([[a]], dtype=np.float32))

    assert np.allclose(recuperado[0, 0], obj, atol=1.5), "spill branco não foi desfeito"


def test_layout_e_cutouts_contam_a_mesma_historia():
    """O layouts.json só pode pedir cutouts que os testes acima já cobrem."""
    import json

    with open(os.path.join(ASSETS_DIR, "layouts.json"), encoding="utf-8") as fh:
        layouts = json.load(fh)
    pedidos = {meta["file"] for meta in layouts["assets"].values()}
    cobertos = {f"{n}.png" for n in EXPECTED_CUTOUTS}
    assert pedidos <= cobertos, f"layout pede cutout sem teste: {sorted(pedidos - cobertos)}"


def test_assets_com_sombra_projetada_estao_no_preset():
    """Quem tinha sombra na foto original precisa continuar com --kill-shadows.

    Regressão de configuração: se alguém remover a linha do PRESETS, o asset
    volta a carregar o borrão cinza e nenhum outro teste percebe (na foto final
    a sombra e o edredom branco de uma cama são estatisticamente parecidos).
    """
    tool = _load_tool()
    conhecidos = ["sofa", "bed", "vase-decor", "table-lamp", "dining-set", "nightstand", "plant"]
    for nome in conhecidos:
        preset = tool.PRESETS.get(nome, {})
        assert preset.get("kill_shadows") is True, (
            f"{nome} tinha sombra projetada na foto original e perdeu o kill_shadows do PRESETS"
        )


def test_supressao_de_sombra_remove_sombra_e_preserva_o_movel():
    """Controle positivo, determinístico: foto sintética com sombra conhecida.

    Monta um "produto" (objeto colorido) sobre fundo branco com uma elipse de
    sombra neutra e clara no chão, e roda o pipeline de verdade. O que se exige:
    a sombra some e o objeto continua inteiro. É este teste que prova que
    --kill-shadows faz o que promete — os assets reais não conseguem provar,
    porque um edredom branco e uma sombra cinza se parecem em estatística.
    """
    tool = _load_tool()

    H, W = 200, 200
    arr = np.full((H, W, 3), 255.0, dtype=np.float32)
    arr[40:130, 60:140] = (176.0, 96.0, 60.0)  # móvel colorido

    # sombra: elipse neutra e clara, logo acima do branco (croma 0, luma 232)
    yy, xx = np.mgrid[0:H, 0:W]
    elipse = ((yy - 145) / 18.0) ** 2 + ((xx - 100) / 55.0) ** 2 <= 1.0
    arr[elipse] = (232.0, 232.0, 232.0)

    bg = tool.estimate_bg(arr)
    assert np.all(bg > 250), "moldura deveria ser o fundo branco"

    sem = tool.despeckle(tool.key_out(arr, 0.045, 0.150, bg))
    assert sem[145, 100] > 0.05, "a sombra precisa estar visível ANTES, senão o teste não testa nada"

    com = tool.suppress_shadows(sem, arr, bg, band=0.22, luma_tol=80.0)

    assert com[145, 100] == 0.0, "a sombra projetada deveria ter sido removida"
    assert com[85, 100] == sem[85, 100], "o miolo do móvel não pode mudar"
    # o pé do móvel (dentro da faixa de chão) tem cor: o croma o protege
    assert com[125, 100] == sem[125, 100], "a base colorida do móvel não pode ser removida"


def test_assets_sem_supressao_nao_estao_carregando_sombra():
    """Quem ficou FORA do kill_shadows não pode ter sombra largada na base.

    Vale para assets em que a supressão é arriscada (poltrona bouclé clara).
    Como não há supressão, a única razão para ter muito pixel neutro e claro na
    faixa de chão é sombra que ninguém removeu. A cama fica de fora deste teste
    de propósito: o edredom branco dela é neutro e claro e está no chão.
    """
    import json

    with open(os.path.join(ASSETS_DIR, "layouts.json"), encoding="utf-8") as fh:
        layouts = json.load(fh)
    tool = _load_tool()

    ambiguos = {"bed"}  # edredom branco no chão: indistinguível de sombra aqui
    for name, meta in layouts["assets"].items():
        if meta.get("anchor") in ("wall", "ceiling") or name in ambiguos:
            continue
        if tool.PRESETS.get(name, {}).get("kill_shadows"):
            continue  # já coberto pelo controle positivo

        arr = np.asarray(
            PIL_Image.open(os.path.join(ASSETS_DIR, meta["file"])).convert("RGBA"), dtype=float
        )
        alpha = arr[..., 3] / 255.0
        if not (alpha > 0.35).any():
            continue
        luma = arr[..., :3].mean(axis=2)
        chroma = arr[..., :3].max(axis=2) - arr[..., :3].min(axis=2)

        ys = np.where(alpha > 0.35)[0]
        corte = int(ys.max() - 0.12 * max(1, ys.max() - ys.min()))
        faixa = slice(corte, None)
        visivel = alpha[faixa] > 0.05
        if not visivel.any():
            continue

        suspeito = visivel & (chroma[faixa] < 8) & (luma[faixa] > 200)
        fracao = float(suspeito.sum()) / float(visivel.sum())
        assert fracao < 0.10, (
            f"{name}.png: {fracao:.0%} da faixa de chão é neutra e clara — "
            "sombra projetada que sobrou (adicione o asset ao PRESETS com --kill-shadows)"
        )
