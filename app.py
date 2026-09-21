"""VideoVortex — backend Flask.

Serve o frontend (tour 360 simulado, staging virtual, estúdio de vídeo) e expõe:

* a API de projetos (salvar/listar/carregar/excluir);
* a API de narração — a única parte que faz trabalho pesado no servidor, porque
  depende de voz neural, cache em disco e medição de duração real do áudio.

O roteiro, o staging e a gravação do vídeo continuam 100% no navegador: nenhum
serviço externo e nenhuma chave de API são necessários para o app funcionar.
A narração cai para uma voz de teste local quando não há internet — ver narrate.py.
"""

import json
import os
import re
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request, send_from_directory

import narrate

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
AUDIO_DIR = narrate.AUDIO_DIR

app = Flask(__name__)


# ---------------------------------------------------------------- utilidades
def _ensure_storage():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(PROJECTS_FILE):
        with open(PROJECTS_FILE, "w", encoding="utf-8") as fh:
            json.dump([], fh)


def _load_projects():
    _ensure_storage()
    try:
        with open(PROJECTS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_projects(projects):
    _ensure_storage()
    tmp = PROJECTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(projects, fh, ensure_ascii=False)
    os.replace(tmp, PROJECTS_FILE)


# ------------------------------------------------------------------- páginas
@app.get("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------- API
@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "app": "video_vortex"})


@app.get("/api/projects")
def list_projects():
    """Lista projetos (sem as fotos embutidas, para a listagem ser leve)."""
    projects = _load_projects()
    slim = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "updatedAt": p.get("updatedAt"),
            "photoCount": len(p.get("photos", [])),
            "title": (p.get("info") or {}).get("titulo", ""),
        }
        for p in projects
    ]
    return jsonify(slim)


@app.post("/api/projects")
def create_project():
    payload = request.get_json(force=True, silent=True) or {}
    projects = _load_projects()
    now = datetime.now(timezone.utc).isoformat()
    project = {
        "id": uuid.uuid4().hex[:12],
        "name": payload.get("name") or "Projeto sem nome",
        "createdAt": now,
        "updatedAt": now,
        "info": payload.get("info", {}),
        "photos": payload.get("photos", []),
        "settings": payload.get("settings", {}),
        "script": payload.get("script", {}),
    }
    projects.append(project)
    _save_projects(projects)
    return jsonify({"id": project["id"], "updatedAt": now}), 201


@app.get("/api/projects/<project_id>")
def get_project(project_id):
    for p in _load_projects():
        if p.get("id") == project_id:
            return jsonify(p)
    return jsonify({"error": "Projeto não encontrado"}), 404


@app.put("/api/projects/<project_id>")
def update_project(project_id):
    payload = request.get_json(force=True, silent=True) or {}
    projects = _load_projects()
    for p in projects:
        if p.get("id") == project_id:
            now = datetime.now(timezone.utc).isoformat()
            p["name"] = payload.get("name", p.get("name"))
            p["updatedAt"] = now
            for key in ("info", "photos", "settings", "script"):
                if key in payload:
                    p[key] = payload[key]
            _save_projects(projects)
            return jsonify({"id": project_id, "updatedAt": now})
    return jsonify({"error": "Projeto não encontrado"}), 404


@app.delete("/api/projects/<project_id>")
def delete_project(project_id):
    projects = [p for p in _load_projects() if p.get("id") != project_id]
    _save_projects(projects)
    return jsonify({"deleted": project_id})


# ------------------------------------------------------------------ narração
# A chave do cache nasce de sha1 e sempre tem este formato; validar a máscara é
# o que impede um ../ de escapar da pasta de áudio ao servir o arquivo.
AUDIO_RE = re.compile(r"^[0-9a-f]{20}\.(mp3|wav)$")


@app.get("/api/narrate/voices")
def narrate_voices():
    """O que esta máquina consegue sintetizar agora (e quanto já está em cache)."""
    return jsonify(narrate.backend_report())


@app.post("/api/narrate")
def narrate_one():
    """Sintetiza um trecho. Devolve a duração medida — é ela que dita o vídeo."""
    payload = request.get_json(force=True, silent=True) or {}
    texto = payload.get("text") or ""
    try:
        res = narrate.synthesize(
            texto,
            voice=payload.get("voice"),
            rate=payload.get("rate") or narrate.DEFAULT_RATE,
            pitch=payload.get("pitch") or narrate.DEFAULT_PITCH,
            backend=payload.get("backend"),
            force=bool(payload.get("force")),
        )
    except narrate.SynthError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({k: v for k, v in res.items() if k != "path"})


@app.post("/api/narrate/batch")
def narrate_batch():
    """Sintetiza o roteiro inteiro: um áudio por trecho, na ordem recebida.

    O roteiro é regerado a cada ajuste de tom/duração, então quase todo trecho já
    chega em cache — o custo por clique é só a leitura do sidecar.
    """
    payload = request.get_json(force=True, silent=True) or {}
    segmentos = payload.get("segments") or []
    if not isinstance(segmentos, list) or not segmentos:
        return jsonify({"error": "envie segments: [{id, text}, ...]"}), 400
    try:
        res = narrate.synthesize_many(
            segmentos,
            voice=payload.get("voice"),
            rate=payload.get("rate") or narrate.DEFAULT_RATE,
            pitch=payload.get("pitch") or narrate.DEFAULT_PITCH,
            backend=payload.get("backend"),
        )
    except narrate.SynthError as exc:
        return jsonify({"error": str(exc)}), 400
    # `backend`/`mock` vêm do narrate medindo o que foi USADO (pode ter caído
    # para a voz de teste no meio do caminho) — não do que foi pedido.
    return jsonify(res)


@app.get("/api/audio/<path:filename>")
def audio_file(filename):
    """Serve o áudio do cache. A máscara da chave basta como autorização."""
    if not AUDIO_RE.match(filename):
        return jsonify({"error": "nome de áudio inválido"}), 400
    return send_from_directory(AUDIO_DIR, filename, conditional=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
