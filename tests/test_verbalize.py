"""Testes do verbalizer (VVScript.verbalize) — o que o TTS vai realmente falar.

O roteiro é escrito para ser LIDO e depois FALADO. Estes testes rodam o
`scriptgen.js` no node e travam a tradução entre as duas coisas: símbolo de
moeda, unidade de medida, %, abreviação e marcador de plural.

O caso mais delicado é o que NÃO se converte — e por isso ele tem teste próprio
aqui embaixo: número solto fica em algarismo, porque em português o numeral
concorda em gênero com o substantivo ("1 vaga" → "uma vaga", "200 vagas" →
"duzentas vagas") e a voz neural resolve isso melhor do que uma tabela nossa.
"""

import json
import os
import shutil
import subprocess

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTGEN_JS = os.path.join(BASE_DIR, "static", "js", "scriptgen.js")

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node não instalado — pulando os testes do verbalizer"
)


def verbalize(entradas: list[str]) -> list[str]:
    """Chama VVScript.verbalize no node e devolve as saídas, na mesma ordem."""
    script = """
    global.window = global;
    require(%s);
    const entradas = JSON.parse(process.argv[1]);
    console.log(JSON.stringify(entradas.map((t) => VVScript.verbalize(t))));
    """ % json.dumps(SCRIPTGEN_JS)
    res = subprocess.run(
        ["node", "-e", script, json.dumps(entradas)],
        capture_output=True, text=True, cwd=BASE_DIR, timeout=60,
    )
    assert res.returncode == 0, f"node falhou:\n{res.stderr}"
    return json.loads(res.stdout.strip().splitlines()[-1])


def extenso(valor: int) -> str:
    script = """
    global.window = global;
    require(%s);
    console.log(JSON.stringify(VVScript.inteiroPorExtenso(%d)));
    """ % (json.dumps(SCRIPTGEN_JS), valor)
    res = subprocess.run(["node", "-e", script], capture_output=True, text=True,
                         cwd=BASE_DIR, timeout=60)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout.strip())


# ------------------------------------------------------------------- unidades
def test_unidade_nao_come_o_numero():
    """Regressão: "78 m²" já virou só "metros quadrados" (número perdido).

    A causa era um grupo de captura a mais na alternância (m²|m2), que deslocava
    o número no callback de replace.
    """
    assert verbalize(["78 m²"]) == ["78 metros quadrados"]
    assert verbalize(["120 m² de terreno"]) == ["120 metros quadrados de terreno"]


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("78 m²", "78 metros quadrados"),
        ("1 m²", "1 metro quadrado"),
        ("5 m3", "5 metros cúbicos"),
        ("3 km²", "3 quilômetros quadrados"),
        ("12 km", "12 quilômetros"),
        ("80 kg", "80 quilos"),
        ("30 cm", "30 centímetros"),
        ("5 mm", "5 milímetros"),
        ("2 m", "2 metros"),
    ],
)
def test_unidades(entrada, esperado):
    assert verbalize([entrada]) == [esperado]


def test_km2_nao_vira_quilometros_quadrado_solto():
    """A ordem da tabela importa: composta antes da simples."""
    assert verbalize(["3 km²"]) == ["3 quilômetros quadrados"]


# --------------------------------------------------------------------- moeda
@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("R$ 650.000", "seiscentos e cinquenta mil reais"),
        ("R$ 1", "um real"),
        ("R$ 2", "dois reais"),
        ("R$ 1.500.000,00", "um milhão e quinhentos mil reais"),
        ("R$ 1.234,56", "mil duzentos e trinta e quatro reais e cinquenta e seis centavos"),
        ("R$ 0,99", "noventa e nove centavos"),
        ("R$ 650000", "seiscentos e cinquenta mil reais"),
    ],
)
def test_moeda(entrada, esperado):
    assert verbalize([entrada]) == [esperado]


@pytest.mark.parametrize(
    "valor,esperado",
    [
        (0, "zero"),
        (1, "um"),
        (14, "quatorze"),
        (15, "quinze"),
        (21, "vinte e um"),
        (100, "cem"),
        (120, "cento e vinte"),
        (234, "duzentos e trinta e quatro"),
        (1000, "mil"),
        (1234, "mil duzentos e trinta e quatro"),          # sem "e": último grupo tem "e" interno
        (1500, "mil e quinhentos"),                        # com "e": último grupo é cem cheio
        (2001, "dois mil e um"),
        (1100, "mil e cem"),
        (1100000, "um milhão e cem mil"),
        (1234567, "um milhão duzentos e trinta e quatro mil quinhentos e sessenta e sete"),
        (2000000, "dois milhões"),
    ],
)
def test_inteiro_por_extenso(valor, esperado):
    """A regra do "e" entre grupos é a parte que erra fácil — cada linha é um caso dela."""
    assert extenso(valor) == esperado


# ---------------------------------------------------------- plural e tempo
def test_marcador_de_plural_resolve_pela_contagem():
    assert verbalize(["2 quarto(s)"]) == ["2 quartos"]
    assert verbalize(["1 quarto(s)"]) == ["1 quarto"]
    assert verbalize(["5 vaga(s)"]) == ["5 vagas"]
    assert verbalize(["2 suit(s)"]) == ["2 suits"]  # sem regra especial: só o "s"


def test_marcador_de_plural_sem_contagem_le_singular():
    assert verbalize(["quarto(s)"]) == ["quarto"]


@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("15s", "15 segundos"),
        ("1s", "1 segundo"),
        ("2min", "2 minutos"),
        ("1h", "1 hora"),
        ("3hs", "3 horas"),
    ],
)
def test_tempo_colado_no_numero(entrada, esperado):
    assert verbalize([entrada]) == [esperado]


# ------------------------------------------------------------- abreviações
@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("apto", "apartamento"),
        ("aptos", "apartamentos"),
        ("2 qto", "2 quarto"),
        ("2 qtos", "2 quartos"),
        ("WC", "banheiro"),
        ("wc", "banheiro"),
        ("nº 42", "número 42"),
        ("sr. corretor", "senhor corretor"),
        ("sra. cliente", "senhora cliente"),
    ],
)
def test_abreviacoes(entrada, esperado):
    assert verbalize([entrada]) == [esperado]


# --------------------------------------------------- símbolos e limpeza
def test_por_cento_e_limpeza_de_marcacao():
    assert verbalize(["50% de entrada"]) == ["50 por cento de entrada"]
    assert verbalize(["**destaque** ✨"]) == ["destaque"]
    assert verbalize(["metro → metrô"]) == ["metro metrô"]
    assert verbalize(["a\n\nb   c"]) == ["a b c"]


def test_numero_solto_fica_em_algarismo_de_proposito():
    """Decisão de design com teste para não ser "corrigida" sem querer.

    Escrever "1 vaga" por extenso daria "um vaga" (gênero errado: é "uma vaga"),
    e "200 vagas" daria "duzentos vagas" (é "duzentas"). A voz neural acerta o
    gênero; a nossa tabela não tem como saber o substantivo. Então o numeral
    solto passa intacto e o verbalizer cuida só do que a voz não sabe ler.
    """
    for frase in ("1 vaga", "2 vagas", "200 vagas", "Rua 7"):
        assert verbalize([frase]) == [frase], f"{frase!r} não deveria ser convertido por extenso"


def test_verbalize_e_idempotente():
    """Rodar duas vezes não pode estragar (o app verbaliza em etapas diferentes)."""
    entradas = [
        "Apartamento com 78 m², 2 quarto(s) e 1 vaga. R$ 650.000 à vista, sr. corretor.",
        "15s de gancho, 50% de entrada, apto com WC",
        "R$ 1.234,56 em 3x",
    ]
    uma = verbalize(entradas)
    duas = verbalize(uma)
    assert uma == duas


def test_texto_vazio_e_robusto():
    assert verbalize(["", "   ", None]) == ["", "", ""]
