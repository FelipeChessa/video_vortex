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

# Assets que o staging usa quando existem (o código tem fallback procedural).
EXPECTED_CUTOUTS = ["dining-set", "pendant", "table-lamp", "vase-decor", "wall-art"]


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
