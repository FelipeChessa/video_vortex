"""Testes da API do VideoVortex (sem dependência de navegador)."""

import json

import app as app_module


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "PROJECTS_FILE", str(tmp_path / "projects.json"))
    monkeypatch.setattr(app_module, "DATA_DIR", str(tmp_path))
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_health(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"


def test_index_renders(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    res = client.get("/")
    assert res.status_code == 200
    assert b"VideoVortex" in res.data


def test_projects_crud(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)

    # lista vazia
    assert client.get("/api/projects").get_json() == []

    # cria
    payload = {
        "name": "Ap 2 quartos — Vila Mariana",
        "info": {"titulo": "Ap aconchegante", "preco": "R$ 650.000"},
        "photos": [{"id": "a1", "label": "Sala", "empty": True}],
        "settings": {"tone": "familiar"},
        "script": {"full": "Roteiro de teste"},
    }
    res = client.post("/api/projects", json=payload)
    assert res.status_code == 201
    project_id = res.get_json()["id"]

    # lista com 1 (versão slim)
    listing = client.get("/api/projects").get_json()
    assert len(listing) == 1
    assert listing[0]["photoCount"] == 1
    assert listing[0]["title"] == "Ap aconchegante"

    # busca completa
    full = client.get(f"/api/projects/{project_id}").get_json()
    assert full["info"]["preco"] == "R$ 650.000"
    assert full["photos"][0]["label"] == "Sala"

    # atualiza
    res = client.put(f"/api/projects/{project_id}", json={"name": "Novo nome"})
    assert res.status_code == 200
    assert client.get(f"/api/projects/{project_id}").get_json()["name"] == "Novo nome"

    # 404 para id inexistente
    assert client.get("/api/projects/nao-existe").status_code == 404

    # exclui
    assert client.delete(f"/api/projects/{project_id}").status_code == 200
    assert client.get("/api/projects").get_json() == []

    # arquivo persistido é JSON válido
    with open(tmp_path / "projects.json", encoding="utf-8") as fh:
        assert json.load(fh) == []
