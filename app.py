"""VideoVortex — backend Flask.

Serve o frontend (tour 360 simulado, staging virtual, estúdio de vídeo)
e expõe uma API simples de projetos (salvar/listar/carregar/excluir).
A geração de roteiro, o staging virtual e a gravação do vídeo rodam
100% no navegador — nenhum serviço externo ou chave de API é necessário.
"""

import json
import os
import uuid
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
