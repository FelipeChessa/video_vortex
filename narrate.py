"""VideoVortex — narração neural em PT-BR, um áudio por trecho, com cache.

Por que existe
--------------
A narração precisa de **duração real** por trecho: é ela que dita o tempo do
vídeo (quem manda no corte não é o número de segundos por foto, é a fala). Então
o servidor sintetiza, mede e guarda o resultado — o navegador só toca.

Três backends, escolhidos automaticamente:

======  ==========================  ==========================================
backend quando entra                 observação
======  ==========================  ==========================================
edge    pacote ``edge-tts`` presente  vozes neurais da Microsoft — **precisa de
                                       internet** (é o caminho de produção)
piper   binário ``piper`` no PATH     offline; exige o modelo ``.onnx``
mock    nenhum dos dois, ou           tom sintético com duração proporcional ao
        ``VV_MOCK_TTS=1``             texto: mantém o pipeline inteiro rodando
                                       em teste/CI/sandbox sem rede
======  ==========================  ==========================================

Se o ``edge`` falhar (sem internet, por exemplo), a síntese **cai para o mock**,
marcando ``fallback: true`` e o motivo na resposta — melhor uma voz de teste do
que um vídeo sem narração. O fallback é lembrado em memória para não tentar a
rede em cada trecho do roteiro.

Cache
-----
``data/audio/<chave>.mp3|wav`` mais um ``<chave>.json`` com os metadados. A chave
é o sha1 de ``backend|voz|rate|pitch|texto``: mudar qualquer um dos cinco gera
outro áudio, e repetir o mesmo pedido custa zero (o roteiro é regerado
constantemente enquanto o corretor ajusta o texto — sem cache isso seria uma
chamada de rede por clique).

O sidecar guarda a duração medida, então o caminho de cache-hit não reabre o
arquivo de áudio.

Duração de áudio sem dependência externa
----------------------------------------
O sandbox não tem ffmpeg, e a duração real é justamente o dado que o vídeo
precisa. Então: WAV pelo módulo ``wave`` da biblioteca padrão, e MP3 por um
leitor de quadros próprio (:func:`mp3_info`) — soma exata de ``amostras / taxa``
quadro a quadro, sem estimar por bitrate médio. O leitor cobre MPEG 1/2/2.5
camadas I–III, pula etiqueta ID3v2 e re-sincroniza se encontrar lixo.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sys
import time
import wave
from array import array
from datetime import datetime, timezone
from math import pi, sin
from struct import pack

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")

# ------------------------------------------------------------------ constantes
DEFAULT_VOICE = "pt-BR-FranciscaNeural"
DEFAULT_RATE = "+0%"
DEFAULT_PITCH = "+0Hz"

# Vozes pt-BR do edge-tts. Lista curada (não catálogo remoto: `list_voices` exige
# rede, e a interface precisa responder mesmo offline).
VOICES = [
    {"id": "pt-BR-FranciscaNeural", "label": "Francisca (feminina, natural)", "gender": "feminino"},
    {"id": "pt-BR-AntonioNeural", "label": "Antônio (masculino, natural)", "gender": "masculino"},
    {"id": "pt-BR-ThalitaMultilingualNeural", "label": "Thalita (feminina, multilíngue)", "gender": "feminino"},
]

# Velocidade de fala usada SÓ pelo mock, para o tempo do vídeo fazer sentido nos
# testes. ~900 caracteres por minuto é o ritmo de narração em PT-BR.
MOCK_CHARS_PER_SECOND = 15.0
MOCK_SAMPLE_RATE = 24000
MOCK_MIN_SECONDS = 0.9

MAX_CHARS = 4000  # acima disso o texto é cortado; o roteiro divide em trechos

# Lembra que o edge falhou, para não pagar o timeout da rede em cada trecho.
_EDGE_BROKEN: str | None = None


class SynthError(RuntimeError):
    """Falha de síntese que merece chegar ao usuário (HTTP 4xx/5xx), não um traceback."""


# --------------------------------------------------------------------- duração
def wav_duration(path: str) -> float | None:
    """Duração de um WAV, pelo cabeçalho (samples / taxa)."""
    try:
        with wave.open(path, "rb") as wf:
            rate = wf.getframerate()
            if not rate:
                return None
            return wf.getnframes() / float(rate)
    except (wave.Error, OSError):
        return None


# Tabelas do MPEG Audio Layer I/II/III. Índice 0 = "free" e 15 = inválido.
_BITRATES = {
    ("1", 1): [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],
    ("1", 2): [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],
    ("1", 3): [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
    ("2", 1): [0, 32, 48, 56, 64, 80, 96, 112, 128, 144, 160, 176, 192, 224, 256],
    ("2", 2): [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160],
}
_BITRATES[("2", 3)] = _BITRATES[("2", 2)]  # MPEG2 e MPEG2.5 compartilham
_SAMPLE_RATES = {"1": [44100, 48000, 32000], "2": [22050, 24000, 16000], "2.5": [11025, 12000, 8000]}


def _frame_header(b0: int, b1: int, b2: int, b3: int) -> dict | None:
    """Decodifica 4 bytes de cabeçalho de quadro. None se não for cabeçalho válido."""
    if b0 != 0xFF or (b1 & 0xE0) != 0xE0:
        return None

    version_bits = (b1 >> 3) & 0x03
    layer_bits = (b1 >> 1) & 0x03
    if version_bits == 0x01 or layer_bits == 0:  # versão reservada / reservado
        return None
    version = {0x03: "1", 0x02: "2", 0x00: "2.5"}[version_bits]
    layer = {0x03: 1, 0x02: 2, 0x01: 3}[layer_bits]

    bitrate_idx = (b2 >> 4) & 0x0F
    rate_idx = (b2 >> 2) & 0x03
    padding = (b2 >> 1) & 0x01
    if bitrate_idx in (0, 15) or rate_idx == 3:
        return None

    bitrate = _BITRATES[(version, layer)][bitrate_idx] * 1000
    sample_rate = _SAMPLE_RATES[version][rate_idx]
    if not bitrate or not sample_rate:
        return None

    if layer == 1:
        samples = 384
    elif layer == 2:
        samples = 1152
    else:
        samples = 1152 if version == "1" else 576

    if layer == 1:
        length = (12 * bitrate // sample_rate + padding) * 4
    else:
        length = (samples // 8) * bitrate // sample_rate + padding
    if length < 4:
        return None

    return {
        "version": version,
        "layer": layer,
        "bitrate": bitrate,
        "sample_rate": sample_rate,
        "padding": padding,
        "samples": samples,
        "length": length,
        "channels": 1 if ((b3 >> 6) & 0x03) == 3 else 2,
    }


def _id3v2_size(data: bytes) -> int:
    """Tamanho da etiqueta ID3v2 no início do arquivo (0 se não houver)."""
    if len(data) < 10 or data[0:3] != b"ID3":
        return 0
    flags = data[5]
    size = (data[6] << 21) | (data[7] << 14) | (data[8] << 7) | data[9]  # "syncsafe"
    total = 10 + size
    if flags & 0x10:  # rodapé presente
        total += 10
    return total


def mp3_info(data: bytes) -> dict | None:
    """Percorre os quadros MP3 e devolve duração e características.

    Soma ``amostras / taxa`` quadro a quadro em vez de estimar por bitrate médio:
    a diferença aparece justamente em arquivo VBR, e o tempo do vídeo é montado
    em cima desse número.
    """
    offset = _id3v2_size(data)
    n = len(data)
    frames = 0
    duration = 0.0
    primeiro = None
    ultimo = None

    while offset + 4 <= n:
        header = _frame_header(data[offset], data[offset + 1], data[offset + 2], data[offset + 3])
        if header is None:
            # re-sincroniza: procura o próximo 0xFF mascarado dentro de uma janela
            limite = min(n - 4, offset + 4096)
            achou = -1
            for pos in range(offset + 1, limite + 1):
                if data[pos] == 0xFF and (data[pos + 1] & 0xE0) == 0xE0:
                    if _frame_header(data[pos], data[pos + 1], data[pos + 2], data[pos + 3]):
                        achou = pos
                        break
            if achou < 0:
                break
            offset = achou
            continue

        if offset + header["length"] > n:
            break  # último quadro truncado

        frames += 1
        duration += header["samples"] / float(header["sample_rate"])
        primeiro = primeiro or header
        ultimo = header
        offset += header["length"]

    if not frames or primeiro is None:
        return None

    return {
        "duration": duration,
        "frames": frames,
        "sample_rate": primeiro["sample_rate"],
        "bitrate": primeiro["bitrate"],
        "version": primeiro["version"],
        "layer": primeiro["layer"],
        "channels": primeiro["channels"],
        "vbr": any(
            h["bitrate"] != primeiro["bitrate"]
            for h in (primeiro, ultimo)
            if h is not None
        ),
        "bytes": n,
    }


def audio_duration(path: str) -> float | None:
    """Duração em segundos, escolhendo o leitor pela extensão."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".wav":
        return wav_duration(path)
    if ext == ".mp3":
        try:
            with open(path, "rb") as fh:
                info = mp3_info(fh.read())
        except OSError:
            return None
        return info["duration"] if info else None
    return None


def estimate_speech_seconds(text: str) -> float:
    """Estimativa de duração pela contagem de caracteres.

    É o que o mock usa e o que a interface mostra antes de sintetizar. Nunca
    substitui a duração medida quando o áudio existe.
    """
    return max(MOCK_MIN_SECONDS, len(text or "") / MOCK_CHARS_PER_SECOND)


# ----------------------------------------------------------------- backends
def _which(name: str) -> str | None:
    return shutil.which(name)


def piper_model() -> str | None:
    """Caminho do modelo do piper (``VV_PIPER_MODEL`` ou o primeiro .onnx em models/)."""
    env = os.environ.get("VV_PIPER_MODEL")
    if env and os.path.exists(env):
        return env
    pasta = os.path.join(BASE_DIR, "models")
    if os.path.isdir(pasta):
        for nome in sorted(os.listdir(pasta)):
            if nome.endswith(".onnx"):
                return os.path.join(pasta, nome)
    return None


def backend_available(backend: str) -> tuple[bool, str]:
    """(disponível, motivo). O motivo vai para a interface — nada de falha silenciosa."""
    if backend == "mock":
        return True, "voz de teste (tom sintético)"
    if backend == "edge":
        if os.environ.get("VV_MOCK_TTS"):
            return False, "VV_MOCK_TTS está definido"
        try:
            import edge_tts  # noqa: F401
        except ImportError:
            return False, "pacote edge-tts não instalado (pip install edge-tts)"
        return True, "edge-tts (vozes neurais; precisa de internet)"
    if backend == "piper":
        exe = _which("piper")
        if not exe:
            return False, "binário piper não encontrado no PATH"
        if not piper_model():
            return False, "modelo .onnx do piper não encontrado (defina VV_PIPER_MODEL)"
        return True, "piper (offline)"
    return False, f"backend desconhecido: {backend}"


def resolve_backend(preferido: str | None = None) -> str:
    """Backend efetivo: pedido → VV_TTS_BACKEND → edge → piper → mock."""
    if os.environ.get("VV_MOCK_TTS"):
        return "mock"
    for nome in (preferido, os.environ.get("VV_TTS_BACKEND"), "edge", "piper", "mock"):
        if nome and backend_available(nome)[0]:
            return nome
    return "mock"


def backend_report() -> dict:
    """Retrato do que está pronto nesta máquina (para /api/narrate/voices)."""
    backends = {}
    for nome in ("edge", "piper", "mock"):
        ok, motivo = backend_available(nome)
        backends[nome] = {"available": ok, "reason": motivo}
    ativo = resolve_backend()
    return {
        "backend": ativo,
        "mock": ativo == "mock",
        "reason": backends[ativo]["reason"],
        "backends": backends,
        "voices": VOICES,
        "default_voice": DEFAULT_VOICE,
        "cache": cache_stats(),
        "edge_failure": _EDGE_BROKEN,
        "chars_per_second": MOCK_CHARS_PER_SECOND,
    }


# ------------------------------------------------------------------- mock
def _mock_synth(text: str, path: str) -> None:
    """Tom sintético com duração proporcional ao texto.

    Não é para soar como voz: é para o pipeline inteiro (cache, duração, mixagem,
    legendas por sentença) poder ser exercitado sem rede. A frequência vem do
    próprio texto, então trechos diferentes soam diferentes e dá para ouvir onde
    um trecho começa.
    """
    segundos = estimate_speech_seconds(text)
    n = int(segundos * MOCK_SAMPLE_RATE)
    semente = int(hashlib.sha1(text.encode("utf-8")).hexdigest()[:8], 16)
    freq = 150.0 + (semente % 90)
    amp = 0.10
    fade = int(0.03 * MOCK_SAMPLE_RATE)

    amostras = array("h")
    for i in range(n):
        # tremolo lento: dá cadência de fala ao tom
        env = amp * (0.75 + 0.25 * sin(2 * pi * 3.1 * i / MOCK_SAMPLE_RATE))
        if i < fade:
            env *= i / fade
        elif i > n - fade:
            env *= max(0.0, (n - i) / fade)
        amostras.append(int(env * 32767 * sin(2 * pi * freq * i / MOCK_SAMPLE_RATE)))

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(MOCK_SAMPLE_RATE)
        wf.writeframes(amostras.tobytes())


# ------------------------------------------------------------------- edge
def _run_async(coro):
    """Roda a corrotina mesmo se já houver um event loop ativo (worker async)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(lambda: asyncio.run(coro)).result()


def _edge_synth(text: str, voice: str, rate: str, pitch: str, path: str) -> None:
    import edge_tts

    async def _save() -> None:
        kwargs = {"voice": voice}
        if rate and rate != DEFAULT_RATE:
            kwargs["rate"] = rate
        if pitch and pitch != DEFAULT_PITCH:
            kwargs["pitch"] = pitch
        try:
            com = edge_tts.Communicate(text, **kwargs)
        except TypeError:
            # versão de edge-tts sem rate/pitch: sintetiza com a voz padrão
            com = edge_tts.Communicate(text, voice=voice)
        await com.save(path)

    _run_async(_save())


# ------------------------------------------------------------------ piper
def _piper_synth(text: str, path: str, modelo: str) -> None:
    import subprocess

    exe = _which("piper")
    if not exe:
        raise SynthError("binário piper não encontrado no PATH")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    proc = subprocess.run(
        [exe, "--model", modelo, "--output_file", path],
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=180,
    )
    if proc.returncode != 0:
        raise SynthError(f"piper falhou: {proc.stderr.decode('utf-8', 'replace')[:300]}")


# ------------------------------------------------------------------- cache
def cache_key(text: str, voice: str, rate: str, pitch: str, backend: str) -> str:
    """Chave do cache: muda se qualquer um dos cinco parâmetros mudar."""
    bruto = "\u0000".join([backend, voice, rate, pitch, text])
    return hashlib.sha1(bruto.encode("utf-8")).hexdigest()[:20]


def _sidecar(key: str) -> str:
    return os.path.join(AUDIO_DIR, key + ".json")


def _ler_sidecar(key: str) -> dict | None:
    try:
        with open(_sidecar(key), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def cache_stats() -> dict:
    """Quantos áudios e quantos bytes estão guardados."""
    if not os.path.isdir(AUDIO_DIR):
        return {"files": 0, "bytes": 0, "seconds": 0.0}
    files = 0
    total = 0
    segundos = 0.0
    for nome in os.listdir(AUDIO_DIR):
        if nome.endswith(".json"):
            continue
        caminho = os.path.join(AUDIO_DIR, nome)
        if not os.path.isfile(caminho):
            continue
        files += 1
        total += os.path.getsize(caminho)
        lado = _ler_sidecar(os.path.splitext(nome)[0])
        if lado and isinstance(lado.get("duration"), (int, float)):
            segundos += float(lado["duration"])
    return {"files": files, "bytes": total, "seconds": round(segundos, 2)}


def clear_cache() -> int:
    """Apaga o cache de áudio. Devolve quantos arquivos saíram."""
    if not os.path.isdir(AUDIO_DIR):
        return 0
    removidos = 0
    for nome in os.listdir(AUDIO_DIR):
        caminho = os.path.join(AUDIO_DIR, nome)
        if os.path.isfile(caminho) and (nome.endswith(".json") or nome.endswith((".mp3", ".wav"))):
            os.remove(caminho)
            removidos += 1
    return removidos


# --------------------------------------------------------------- síntese
def synthesize(
    text: str,
    voice: str | None = None,
    rate: str = DEFAULT_RATE,
    pitch: str = DEFAULT_PITCH,
    backend: str | None = None,
    force: bool = False,
) -> dict:
    """Gera (ou reaproveita) o áudio de um trecho.

    Devolve ``{key, path, url, duration, ext, backend, cached, chars, fallback, reason}``.
    ``duration`` é sempre medida no arquivo final — é o número em que o vídeo se
    apoia, então não vale estimar.
    """
    global _EDGE_BROKEN

    texto = " ".join((text or "").split())
    if not texto:
        raise SynthError("texto vazio")
    if len(texto) > MAX_CHARS:
        raise SynthError(f"trecho com {len(texto)} caracteres (máximo {MAX_CHARS}) — divida em partes")

    voz = voice or DEFAULT_VOICE
    escolhido = resolve_backend(backend)
    fallback = False
    motivo = ""

    # Com o edge quebrado (rede bloqueada), nem tenta: cai direto no mock.
    if escolhido == "edge" and _EDGE_BROKEN:
        motivo = f"edge indisponível: {_EDGE_BROKEN}"
        escolhido, fallback = "mock", True

    key = cache_key(texto, voz, rate, pitch, escolhido)
    ext = "mp3" if escolhido in ("edge", "piper") else "wav"
    if escolhido == "piper":
        ext = "wav"
    destino = os.path.join(AUDIO_DIR, f"{key}.{ext}")

    if not force and os.path.exists(destino):
        lado = _ler_sidecar(key)
        duracao = lado.get("duration") if lado else audio_duration(destino)
        if duracao is None:
            duracao = audio_duration(destino)
        if duracao is None:
            os.remove(destino)  # arquivo ilegível: sintetiza de novo
        else:
            return {
                "key": key,
                "path": destino,
                "url": f"/api/audio/{key}.{ext}",
                "duration": round(float(duracao), 3),
                "ext": ext,
                "backend": (lado or {}).get("backend", escolhido),
                "cached": True,
                "chars": len(texto),
                "words": len(texto.split()),
                # o áudio em cache é o MESMO de antes: se ele nasceu de uma queda
                # para a voz de teste, isso continua valendo no cache-hit. Sem
                # persistir, o segundo pedido diria "voz neural" sobre o mesmo bipe.
                "fallback": bool((lado or {}).get("fallback", False)),
                "reason": (lado or {}).get("reason", ""),
            }

    os.makedirs(AUDIO_DIR, exist_ok=True)
    bruto = os.path.join(AUDIO_DIR, f".{key}.part")

    try:
        if escolhido == "edge":
            _edge_synth(texto, voz, rate, pitch, destino)
        elif escolhido == "piper":
            _piper_synth(texto, destino, piper_model() or "")
        else:
            _mock_synth(texto, destino)
    except Exception as exc:  # noqa: BLE001 — qualquer falha de backend cai no mock
        if escolhido == "mock":
            raise SynthError(f"falha ao sintetizar: {exc}") from exc
        if escolhido == "edge":
            _EDGE_BROKEN = str(exc)[:200]
        # limpa o que ficou pela metade e refaz como mock
        for caminho in (destino, bruto):
            if os.path.exists(caminho):
                os.remove(caminho)
        motivo = f"{escolhido} falhou ({str(exc)[:120]}) — usando voz de teste"
        escolhido, fallback, ext = "mock", True, "wav"
        key = cache_key(texto, voz, rate, pitch, escolhido)
        destino = os.path.join(AUDIO_DIR, f"{key}.{ext}")
        if os.path.exists(destino) and not force:
            duracao = audio_duration(destino)
            if duracao:
                return {
                    "key": key, "path": destino, "url": f"/api/audio/{key}.{ext}",
                    "duration": round(float(duracao), 3), "ext": ext, "backend": "mock",
                    "cached": True, "chars": len(texto), "words": len(texto.split()),
                    "fallback": True, "reason": motivo,
                }
            # (o sidecar deste caminho é reescrito logo abaixo, com o mesmo motivo)
        _mock_synth(texto, destino)

    duracao = audio_duration(destino)
    if duracao is None:
        raise SynthError("não consegui medir a duração do áudio gerado")

    with open(_sidecar(key), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "key": key,
                "text": texto,
                "voice": voz,
                "rate": rate,
                "pitch": pitch,
                "backend": escolhido,
                "fallback": fallback,
                "reason": motivo,
                "ext": ext,
                "duration": round(float(duracao), 4),
                "bytes": os.path.getsize(destino),
                "chars": len(texto),
                "created": datetime.now(timezone.utc).isoformat(),
            },
            fh,
            ensure_ascii=False,
            indent=2,
        )

    return {
        "key": key,
        "path": destino,
        "url": f"/api/audio/{key}.{ext}",
        "duration": round(float(duracao), 3),
        "ext": ext,
        "backend": escolhido,
        "cached": False,
        "chars": len(texto),
        "words": len(texto.split()),
        "fallback": fallback,
        "reason": motivo,
    }


def synthesize_many(segmentos: list[dict], **kwargs) -> dict:
    """Sintetiza vários trechos (um áudio por trecho) e soma as durações.

    Cada item de ``segmentos`` precisa de ``text`` e pode ter ``id``. A ordem da
    resposta é a mesma da entrada — o vídeo depende dela.
    """
    saida = []
    total = 0.0
    efetivos = []
    motivos = []
    algum_fallback = False

    for seg in segmentos:
        res = synthesize(seg.get("text", ""), **kwargs)
        efetivos.append(res["backend"])
        if res["fallback"]:
            algum_fallback = True
        if res["reason"] and res["reason"] not in motivos:
            motivos.append(res["reason"])
        item = {
            "id": seg.get("id"),
            "key": res["key"],
            "url": res["url"],
            "duration": res["duration"],
            "chars": res["chars"],
            "cached": res["cached"],
            "backend": res["backend"],
            "fallback": res["fallback"],
        }
        total += res["duration"]
        saida.append(item)

    # O backend relatado é o que REALMENTE falou, não o pedido: se o edge não tem
    # internet e o trecho virou voz de teste, a interface precisa saber — senão ela
    # anuncia "voz neural pronta" enquanto o usuário ouve um bipe.
    efetivo = max(set(efetivos), key=efetivos.count) if efetivos else "mock"
    return {
        "segments": saida,
        "total_duration": round(total, 3),
        "backend": efetivo,
        "mock": any(b == "mock" for b in efetivos),
        "fallback": algum_fallback,
        "reason": motivos[0] if motivos else "",
        "effective_backends": {"edge": efetivos.count("edge"), "piper": efetivos.count("piper"),
                               "mock": efetivos.count("mock")},
    }


# ---------------------------------------------------------------------- CLI
def _cmd_status(args) -> int:
    rep = backend_report()
    print(f"backend ativo : {rep['backend']}  ({rep['reason']})")
    for nome, info in rep["backends"].items():
        marca = "ok " if info["available"] else "-- "
        print(f"  {marca}{nome:<6} {info['reason']}")
    if rep["edge_failure"]:
        print(f"  ! edge falhou antes nesta sessão: {rep['edge_failure']}")
    c = rep["cache"]
    print(f"cache         : {c['files']} áudios, {c['seconds']:.1f}s, {c['bytes'] / 1024:.0f} KB")
    print(f"pasta         : {AUDIO_DIR}")
    return 0


def _cmd_say(args) -> int:
    texto = args.text
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            texto = fh.read()
    if not texto:
        print("informe --text ou --file", file=sys.stderr)
        return 2
    inicio = time.time()
    res = synthesize(texto, voice=args.voice, backend=args.backend, force=args.force)
    print(
        f"{'cache' if res['cached'] else 'novo '} | {res['duration']:6.2f}s | "
        f"{res['backend']:<4} | {res['chars']:>4} car | {res['path']}  "
        f"({time.time() - inicio:.2f}s de relógio)"
    )
    if res["reason"]:
        print(f"  ! {res['reason']}")
    return 0


def _cmd_cache(args) -> int:
    if args.clear:
        print(f"{clear_cache()} arquivos removidos")
    c = cache_stats()
    print(f"{c['files']} áudios, {c['seconds']:.1f}s de fala, {c['bytes'] / 1024:.0f} KB em {AUDIO_DIR}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="o que está disponível nesta máquina").set_defaults(func=_cmd_status)

    say = sub.add_parser("say", help="sintetiza um texto")
    say.add_argument("--text")
    say.add_argument("--file")
    say.add_argument("--voice", default=None)
    say.add_argument("--backend", default=None)
    say.add_argument("--force", action="store_true", help="ignora o cache")
    say.set_defaults(func=_cmd_say)

    cache = sub.add_parser("cache", help="estatísticas do cache")
    cache.add_argument("--clear", action="store_true")
    cache.set_defaults(func=_cmd_cache)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
