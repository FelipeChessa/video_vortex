"""Testes da narração: leitura de duração, backends, cache e API.

A duração real do áudio é o dado em que o vídeo inteiro se apoia, então ela é
testada com arquivos construídos à mão (quadro a quadro de MP3), e não com
arquivos de verdade que o repositório teria de carregar. Isso permite conferir a
soma exata de amostras por quadro, o pulo da etiqueta ID3v2 e a re-sincronização
depois de lixo — casos que não aparecem num arquivo feliz.

A síntese em si roda sempre em mock (``VV_MOCK_TTS=1``): o sandbox não tem rede,
e o objetivo aqui é o pipeline (cache, duração, ordem), não a voz.
"""

import json
import os
import shutil
import subprocess
import wave

import pytest

import narrate

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------------------------------- MP3 sintético
# MPEG1 Layer III, 128 kbps, 44100 Hz, mono, sem padding
H_MPEG1 = bytes([0xFF, 0xFB, 0x90, 0xC0])
LEN_MPEG1 = 417                     # 144 * 128000 // 44100
DUR_MPEG1 = 1152 / 44100            # amostras por quadro / taxa do quadro

# MPEG2 Layer III, 48 kbps, 24000 Hz, mono — o formato que o edge-tts entrega
H_MPEG2 = bytes([0xFF, 0xF3, 0x64, 0xC0])
LEN_MPEG2 = 144                     # (576/8) * 48000 // 24000
DUR_MPEG2 = 576 / 24000


def mp3_com_quadros(header: bytes, tamanho: int, n: int, lixo_entre: int = 0) -> bytes:
    """N quadros de MP3 com cabeçalho válido (e opcionalmente lixo entre eles)."""
    corpo = header + b"\x00" * (tamanho - 4)
    pedacos = [corpo] * n
    if lixo_entre:
        sep = b"\x00" * lixo_entre
        pedacos = [p + sep for p in pedacos[:-1]] + [pedacos[-1]]
    return b"".join(pedacos)


def test_mp3_duracao_mpeg1():
    """Duração = soma de amostras/taxa por quadro, não estimativa por bitrate."""
    info = narrate.mp3_info(mp3_com_quadros(H_MPEG1, LEN_MPEG1, 40))
    assert info is not None
    assert info["frames"] == 40
    assert info["duration"] == pytest.approx(40 * DUR_MPEG1, rel=1e-9)
    assert info["sample_rate"] == 44100
    assert info["bitrate"] == 128000
    assert info["channels"] == 1
    assert info["vbr"] is False


def test_mp3_duracao_mpeg2_24khz():
    """O formato do edge-tts: MPEG2, 24 kHz, 576 amostras por quadro."""
    info = narrate.mp3_info(mp3_com_quadros(H_MPEG2, LEN_MPEG2, 100))
    assert info is not None
    assert info["frames"] == 100
    assert info["duration"] == pytest.approx(100 * DUR_MPEG2, rel=1e-9)
    assert info["version"] == "2"
    assert info["sample_rate"] == 24000


def test_mp3_pula_etiqueta_id3v2():
    """Etiqueta ID3v2 no começo não pode virar quadro nem deslocar a contagem."""
    corpo = mp3_com_quadros(H_MPEG1, LEN_MPEG1, 25)
    # tamanho "syncsafe" (7 bits por byte): 1000 = (7 << 7) | 104
    etiqueta = b"ID3\x04\x00\x00" + bytes([0, 0, 7, 104]) + b"\x00" * 1000
    assert narrate._id3v2_size(etiqueta) == 1010

    info = narrate.mp3_info(etiqueta + corpo)
    assert info is not None
    assert info["frames"] == 25
    assert info["duration"] == pytest.approx(25 * DUR_MPEG1, rel=1e-9)


def test_mp3_resincroniza_depois_de_lixo():
    """Bytes soltos entre quadros: o leitor reencontra o sincronismo e conta tudo."""
    info = narrate.mp3_info(mp3_com_quadros(H_MPEG1, LEN_MPEG1, 30, lixo_entre=7))
    assert info is not None
    assert info["frames"] == 30


def test_mp3_ignora_quadro_truncado_no_fim():
    """Arquivo cortado no meio de um quadro: conta os inteiros, sem estourar."""
    corpo = mp3_com_quadros(H_MPEG1, LEN_MPEG1, 10) + H_MPEG1 + b"\x00" * 50
    info = narrate.mp3_info(corpo)
    assert info is not None
    assert info["frames"] == 10


def test_mp3_lixo_puro_nao_vira_duracao():
    assert narrate.mp3_info(b"\x01\x02\x03\x04" * 100) is None


def test_mp3_cabecalho_reservado_e_recusado():
    """Versão reservada / bitrate inválido não podem ser aceitos como quadro."""
    assert narrate._frame_header(0xFF, 0xEB, 0x90, 0xC0) is None   # versão reservada (bits 01)
    assert narrate._frame_header(0xFF, 0xFB, 0xF0, 0xC0) is None   # bitrate index 15
    assert narrate._frame_header(0xFF, 0xFB, 0x9C, 0xC0) is None   # taxa de amostragem 3
    assert narrate._frame_header(0x00, 0xFB, 0x90, 0xC0) is None   # sem sincronismo


def test_wav_duracao_exata(tmp_path):
    caminho = tmp_path / "x.wav"
    with wave.open(str(caminho), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(b"\x00\x00" * 36000)  # 1,5 s
    assert narrate.wav_duration(str(caminho)) == pytest.approx(1.5)


def test_audio_duration_escolhe_pelo_sufixo(tmp_path):
    assert narrate.audio_duration(str(tmp_path / "nao-existe.wav")) is None
    assert narrate.audio_duration(str(tmp_path / "nao-existe.ogg")) is None


# ------------------------------------------------------------------- backend
@pytest.fixture
def audio_tmp(tmp_path, monkeypatch):
    """Isola o cache de áudio em pasta temporária (nada de sujar data/audio)."""
    pasta = tmp_path / "audio"
    monkeypatch.setattr(narrate, "AUDIO_DIR", str(pasta))
    monkeypatch.setenv("VV_MOCK_TTS", "1")
    monkeypatch.setattr(narrate, "_EDGE_BROKEN", None)
    return pasta


def test_mock_sintetiza_wav_com_duracao_proporcional(audio_tmp):
    texto = "Apartamento de setenta e oito metros quadrados com varanda gourmet."
    res = narrate.synthesize(texto)

    assert res["backend"] == "mock"
    assert res["cached"] is False
    assert os.path.exists(res["path"])
    assert res["url"].startswith("/api/audio/")

    with wave.open(res["path"], "rb") as wf:
        assert wf.getframerate() == narrate.MOCK_SAMPLE_RATE
        assert wf.getnframes() == int(narrate.estimate_speech_seconds(texto) * narrate.MOCK_SAMPLE_RATE)

    # a duração medida bate com o áudio gravado
    assert res["duration"] == pytest.approx(narrate.estimate_speech_seconds(texto), abs=0.01)


def test_cache_reaproveita_e_grava_metadados(audio_tmp):
    primeiro = narrate.synthesize("Bom dia para você.")
    assert primeiro["cached"] is False

    segundo = narrate.synthesize("Bom dia para você.")
    assert segundo["cached"] is True
    assert segundo["key"] == primeiro["key"]
    assert segundo["duration"] == primeiro["duration"]

    with open(narrate._sidecar(primeiro["key"]), encoding="utf-8") as fh:
        meta = json.load(fh)
    assert meta["text"] == "Bom dia para você."
    assert meta["backend"] == "mock"
    assert meta["duration"] == pytest.approx(primeiro["duration"], abs=0.01)


def test_chave_muda_com_texto_voz_ou_ritmo(audio_tmp):
    base = narrate.synthesize("Texto de referência.")
    assert narrate.synthesize("Outro texto qualquer.")["key"] != base["key"]
    assert narrate.synthesize("Texto de referência.", voice="pt-BR-AntonioNeural")["key"] != base["key"]
    assert narrate.synthesize("Texto de referência.", rate="+20%")["key"] != base["key"]
    assert narrate.synthesize("Texto de referência.", pitch="+5Hz")["key"] != base["key"]


def test_force_ignora_o_cache(audio_tmp):
    narrate.synthesize("Repetir.")
    assert narrate.synthesize("Repetir.")["cached"] is True
    assert narrate.synthesize("Repetir.", force=True)["cached"] is False


def test_texto_vazio_ou_longo_demais_da_erro(audio_tmp):
    with pytest.raises(narrate.SynthError):
        narrate.synthesize("   ")
    with pytest.raises(narrate.SynthError):
        narrate.synthesize("palavra " * (narrate.MAX_CHARS // 3))


def test_normaliza_espaco_antes_de_gerar(audio_tmp):
    """Quebras de linha do roteiro não podem criar áudios diferentes do mesmo texto."""
    a = narrate.synthesize("Frase   com\n\nquebras de linha.")
    b = narrate.synthesize("Frase com quebras de linha.")
    assert a["key"] == b["key"]
    assert b["cached"] is True


def test_synthesize_many_preserva_ordem_e_soma(audio_tmp):
    segmentos = [
        {"id": "s1", "text": "Primeiro trecho do roteiro."},
        {"id": "s2", "text": "Segundo trecho, um pouco mais longo que o primeiro."},
        {"id": "s3", "text": "Terceiro."},
    ]
    res = narrate.synthesize_many(segmentos)

    assert [s["id"] for s in res["segments"]] == ["s1", "s2", "s3"]
    assert res["backend"] == "mock"
    assert res["total_duration"] == pytest.approx(
        sum(s["duration"] for s in res["segments"]), abs=0.01
    )
    # a duração total é a do vídeo: tem que ser maior que a fala mais longa
    assert res["total_duration"] > max(s["duration"] for s in res["segments"])


# ------------------------------------------------------- fallback do edge
def test_falha_do_edge_cai_para_mock_com_motivo(audio_tmp, monkeypatch):
    """Sem internet o app não pode ficar sem narração — e precisa dizer o porquê."""
    monkeypatch.delenv("VV_MOCK_TTS", raising=False)
    monkeypatch.setattr(narrate, "backend_available", lambda b: (b == "edge", "teste"))

    tentativas = []

    def edge_quebrado(*a, **kw):
        tentativas.append(1)
        raise OSError("Cannot connect to host speech.platform.bing.com:443")

    monkeypatch.setattr(narrate, "_edge_synth", edge_quebrado)

    res = narrate.synthesize("Teste de queda do backend neural.")
    assert res["backend"] == "mock"
    assert res["fallback"] is True
    assert "edge falhou" in res["reason"]
    assert os.path.exists(res["path"])
    assert len(tentativas) == 1

    # depois da falha, não tenta mais a rede (o roteiro tem dezenas de trechos)
    res2 = narrate.synthesize("Segundo trecho, agora sem tentar a rede de novo.")
    assert res2["backend"] == "mock"
    assert res2["fallback"] is True
    assert len(tentativas) == 1, "não deveria tentar o edge outra vez nesta sessão"


def test_vv_mock_tts_forca_mock(monkeypatch):
    monkeypatch.setenv("VV_MOCK_TTS", "1")
    assert narrate.resolve_backend() == "mock"
    assert narrate.resolve_backend(preferido="edge") == "mock"
    rep = narrate.backend_report()
    assert rep["mock"] is True
    assert rep["backends"]["edge"]["available"] is False
    assert "VV_MOCK_TTS" in rep["backends"]["edge"]["reason"]


def test_resolve_backend_respeita_a_escolha(monkeypatch):
    monkeypatch.delenv("VV_MOCK_TTS", raising=False)
    monkeypatch.setattr(narrate, "backend_available", lambda b: (b == "piper", "teste"))
    assert narrate.resolve_backend(preferido="piper") == "piper"
    # pedir um backend indisponível não pode derrubar: escolhe o próximo que existe
    assert narrate.resolve_backend(preferido="edge") == "piper"


def test_limpar_cache(audio_tmp):
    narrate.synthesize("Um trecho qualquer.")
    narrate.synthesize("Outro trecho.")
    antes = narrate.cache_stats()
    assert antes["files"] == 2
    assert antes["seconds"] > 0

    removidos = narrate.clear_cache()
    assert removidos >= 2  # 2 áudios + 2 sidecars
    assert narrate.cache_stats()["files"] == 0


# ------------------------------------------------------------------- API
@pytest.fixture
def client(tmp_path, monkeypatch):
    import app as app_module

    pasta = tmp_path / "audio"
    monkeypatch.setattr(narrate, "AUDIO_DIR", str(pasta))
    monkeypatch.setattr(app_module, "AUDIO_DIR", str(pasta))
    monkeypatch.setenv("VV_MOCK_TTS", "1")
    monkeypatch.setattr(narrate, "_EDGE_BROKEN", None)
    monkeypatch.setattr(app_module, "PROJECTS_FILE", str(tmp_path / "projects.json"))
    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path))
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_api_voices(client):
    res = client.get("/api/narrate/voices")
    assert res.status_code == 200
    corpo = res.get_json()
    assert corpo["backend"] == "mock"
    assert corpo["mock"] is True
    assert corpo["default_voice"] in [v["id"] for v in corpo["voices"]]
    assert "cache" in corpo


def test_api_narrate_e_serve_o_audio(client):
    res = client.post("/api/narrate", json={"text": "Olá, este é um teste de narração."})
    assert res.status_code == 200
    corpo = res.get_json()
    assert corpo["duration"] > 0
    assert corpo["backend"] == "mock"
    assert "path" not in corpo, "o caminho absoluto não deve vazar na resposta"

    audio = client.get(corpo["url"])
    assert audio.status_code == 200
    assert len(audio.data) > 1000
    assert audio.data[:4] == b"RIFF"  # WAV de verdade

    # segunda chamada vem do cache
    denovo = client.post("/api/narrate", json={"text": "Olá, este é um teste de narração."})
    assert denovo.get_json()["cached"] is True


def test_api_narrate_texto_vazio_da_400(client):
    res = client.post("/api/narrate", json={"text": "  "})
    assert res.status_code == 400
    assert "vazio" in res.get_json()["error"]


def test_api_audio_recusa_nome_fora_da_mascara(client):
    """A máscara da chave é o que impede ../ de escapar da pasta de áudio."""
    for nome in ("../../etc/passwd", "abc.wav", "naoexiste000000000000.mp3", "12345.wav"):
        res = client.get(f"/api/audio/{nome}")
        assert res.status_code in (400, 404), f"{nome} deveria ser recusado"


def test_api_batch_do_roteiro(client):
    segmentos = [
        {"id": "a", "text": "Começamos o tour pela sala de estar."},
        {"id": "b", "text": "Agora, o quarto principal."},
    ]
    res = client.post("/api/narrate/batch", json={"segments": segmentos})
    assert res.status_code == 200
    corpo = res.get_json()
    assert [s["id"] for s in corpo["segments"]] == ["a", "b"]
    assert corpo["total_duration"] == pytest.approx(
        sum(s["duration"] for s in corpo["segments"]), abs=0.01
    )
    assert corpo["mock"] is True

    # todos os áudios existem de verdade e podem ser baixados
    for seg in corpo["segments"]:
        assert client.get(seg["url"]).status_code == 200


def test_api_batch_sem_segmentos_da_400(client):
    assert client.post("/api/narrate/batch", json={}).status_code == 400
    assert client.post("/api/narrate/batch", json={"segments": []}).status_code == 400


def test_roteiro_de_verdade_vira_narracao(client):
    """Corrente inteira: roteiro gerado → verbalizer (node) → TTS → durações.

    É o teste que responde "isso funciona de ponta a ponta?". As peças têm testes
    próprios, mas só juntas elas provam o caminho real do usuário: o corretor gera
    o roteiro, clica em ouvir e recebe áudio na ordem certa — sem nenhum "m²" ou
    "R$" chegando cru na voz.
    """
    if shutil.which("node") is None:
        pytest.skip("node não instalado")

    from PIL import Image  # noqa: F401  (garante que o ambiente tem as libs dos outros testes)

    info = {
        "titulo": "Apartamento 2 quartos com varanda gourmet",
        "tipo": "Apartamento", "endereco": "Vila Mariana, São Paulo", "area": "78",
        "quartos": 2, "banheiros": 1, "vagas": 1, "preco": "R$ 650.000",
        "diferenciais": "Varanda gourmet com churrasqueira\nPerto do metrô",
        "corretor": "Felipe", "contato": "(11) 99999-0000",
    }
    fotos = [
        {"id": "p1", "label": "Sala de estar", "empty": True},
        {"id": "p2", "label": "Quarto principal", "empty": False},
        {"id": "p3", "label": "Cozinha", "empty": False},
    ]

    script_js = """
    global.window = global;
    require(%s);
    const info = JSON.parse(process.argv[1]);
    const fotos = JSON.parse(process.argv[2]);
    const s = VVScript.generate(info, fotos, "persuasivo", 60, 0);
    console.log(JSON.stringify(s.lines.map((l) => VVScript.verbalize(l.text))));
    """ % json.dumps(os.path.join(BASE_DIR, "static", "js", "scriptgen.js"))

    proc = subprocess.run(
        ["node", "-e", script_js, json.dumps(info, ensure_ascii=False), json.dumps(fotos)],
        capture_output=True, text=True, cwd=BASE_DIR, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    falado = json.loads(proc.stdout.strip().splitlines()[-1])

    assert len(falado) >= 4, "o roteiro deveria ter várias linhas faladas"

    # o verbalizer não pode deixar símbolo que a voz leria errado
    for texto in falado:
        assert "m²" not in texto and "m3" not in texto, f"unidade crua no texto falado: {texto!r}"
        assert "R$" not in texto, f"cifrão cru no texto falado: {texto!r}"
        assert "(s)" not in texto, f"marcador de plural cru: {texto!r}"

    # e o roteiro inteiro precisa mencionar o preço por extenso em algum trecho
    assert any("reais" in t for t in falado), "o preço deveria aparecer por extenso"

    segmentos = [{"id": f"l{i}", "text": t} for i, t in enumerate(falado)]
    res = client.post("/api/narrate/batch", json={"segments": segmentos})
    assert res.status_code == 200
    corpo = res.get_json()

    assert [s["id"] for s in corpo["segments"]] == [f"l{i}" for i in range(len(falado))]
    assert corpo["total_duration"] > 0
    for seg in corpo["segments"]:
        assert seg["duration"] > 0
        assert client.get(seg["url"]).status_code == 200

    # "a narração dita o tempo": a soma das durações medidas é o tempo do vídeo
    assert corpo["total_duration"] == pytest.approx(
        sum(s["duration"] for s in corpo["segments"]), abs=0.05
    )
    # um roteiro de 60 s narrado tem que dar algo próximo disso, não 3 s nem 10 min
    assert 20 < corpo["total_duration"] < 180, corpo["total_duration"]


def test_verbalizer_roda_antes_do_tts_no_servidor(client):
    """O servidor sintetiza o texto que recebe — quem verbaliza é o cliente.

    Trava a divisão de responsabilidade: se alguém passar a exigir texto já
    tratado, ou achar que o backend "limpa" sozinho, o teste mostra que o texto
    cru chegaria cru na voz.
    """
    cru = "Apartamento com 78 m² por R$ 650.000"
    res = client.post("/api/narrate", json={"text": cru})
    assert res.status_code == 200

    key = res.get_json()["key"]
    with open(narrate._sidecar(key), encoding="utf-8") as fh:
        meta = json.load(fh)
    assert meta["text"] == cru, "o backend não deve alterar o texto recebido"


def test_lote_reporta_o_backend_efetivo_e_nao_o_pedido(audio_tmp, monkeypatch):
    """Bug pego testando o caminho HTTP de verdade.

    O lote devolvia o backend PEDIDO ("edge") mesmo depois de cada trecho cair para
    a voz de teste — a interface então anunciava "voz neural pronta" enquanto o
    usuário ouvia um bipe. Quem manda no relatório é o que realmente falou.
    """
    monkeypatch.delenv("VV_MOCK_TTS", raising=False)
    monkeypatch.setattr(narrate, "backend_available", lambda b: (b == "edge", "teste"))

    def edge_quebrado(*a, **kw):
        raise OSError("sem rota para o host")

    monkeypatch.setattr(narrate, "_edge_synth", edge_quebrado)

    res = narrate.synthesize_many([
        {"id": "a", "text": "Primeiro trecho."},
        {"id": "b", "text": "Segundo trecho."},
    ])

    assert res["backend"] == "mock"
    assert res["mock"] is True
    assert res["fallback"] is True
    assert res["reason"], "o motivo da queda precisa chegar na interface"
    assert res["effective_backends"]["mock"] == 2
    assert res["effective_backends"]["edge"] == 0
    assert all(seg["backend"] == "mock" and seg["fallback"] is True for seg in res["segments"])


def test_lote_em_mock_puro_nao_e_fallback(audio_tmp):
    """VV_MOCK_TTS=1 é escolha explícita: é voz de teste, mas não é FALHA."""
    res = narrate.synthesize_many([{"id": "a", "text": "Trecho em modo de teste."}])
    assert res["backend"] == "mock"
    assert res["mock"] is True
    assert res["fallback"] is False
    assert res["reason"] == ""


def test_fallback_sobrevive_ao_cache(audio_tmp, monkeypatch):
    """O áudio em cache é o mesmo bipe: não pode ser anunciado como voz neural.

    A chave do cache inclui o backend (`mock` depois da queda), então o segundo
    pedido encontra o arquivo e responde pelo sidecar. Se o sidecar não guardasse
    o `fallback`, o segundo pedido diria "voz neural" sobre o mesmo áudio de teste.
    """
    monkeypatch.delenv("VV_MOCK_TTS", raising=False)
    monkeypatch.setattr(narrate, "backend_available", lambda b: (b == "edge", "teste"))
    monkeypatch.setattr(narrate, "_edge_synth", lambda *a, **kw: (_ for _ in ()).throw(OSError("sem rota")))

    primeiro = narrate.synthesize("Trecho que vai cair para a voz de teste.")
    assert primeiro["fallback"] is True

    segundo = narrate.synthesize("Trecho que vai cair para a voz de teste.")
    assert segundo["cached"] is True
    assert segundo["backend"] == "mock"
    assert segundo["fallback"] is True, "cache-hit não pode esconder que o áudio é voz de teste"
    assert segundo["reason"], "o motivo continua valendo para o mesmo áudio"
