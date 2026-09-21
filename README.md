# 🌀 VideoVortex

Aplicativo web que transforma **fotos de imóveis + informações do imóvel** em:

1. 📝 **Roteiro de venda e apresentação** (com minutagem, 5 tons de voz, gancho 15s, legenda p/ redes e pitch de WhatsApp)
2. 🌀 **Tour com simulação 360°** pelo imóvel (panorâmica contínua, tour automático, tela cheia)
3. ✨ **Staging virtual**: ambientes vazios ganham **mobilia simulada automática** (sofá, cama, mesa, plantas, luminárias…) em 4 estilos — com modo **Antes/Depois**
4. 🎬 **Vídeo do tour** gravado no navegador (movimento Ken Burns, transições, cartões, legendas, marca d'água e trilha ambiente) + arquivo `.srt`

Tudo roda **100% local, sem chave de API e sem serviços externos**: o roteiro é gerado por um motor de templates em PT-BR, o staging é desenhado em canvas e o vídeo é renderizado + gravado via `MediaRecorder` no próprio navegador.

## 🚀 Como rodar

```bash
# 1. (opcional) crie um ambiente virtual
python3 -m venv .venv && source .venv/bin/activate

# 2. instale as dependências
pip install -r requirements.txt

# 3. rode o servidor
python app.py
# ou: gunicorn -b 0.0.0.0:5000 app:app

# 4. abra no navegador
# http://localhost:5000
```

> Sem fotos em mãos? Na etapa 1, clique em **“🎲 Gerar fotos demo”** — o app cria 4 ambientes procedurais para testar o fluxo completo.

## 🧭 Fluxo de uso

| Etapa | O que fazer |
|-------|-------------|
| **1. Fotos** | Envie as fotos na ordem do tour, nomeie cada ambiente e marque **“Vazio? mobiliar ✨”** nos cômodos vazios |
| **2. Dados** | Título, tipo, endereço, área, quartos, banheiros, vagas, preço, diferenciais, corretor e contato |
| **3. Roteiro** | Escolha tom (persuasivo, luxo, familiar, investidor, jovem) e duração (~30/60/90s); regenere variações; **ouça a narração**; copie/baixe |
| **4. Tour 360°** | Assista à simulação 360°, ative o **staging** no estilo desejado (moderno, minimalista, rústico, luxo) e compare **Antes/Depois** |
| **5. Vídeo** | Configure resolução, segundos por foto, cartões, legendas e trilha → **Gravar vídeo** → baixe `.webm` + `.srt` |

Os projetos podem ser **salvos no servidor** (botão 💾 no topo) e reabertos depois.

## 🛠 Arquitetura

```
video_vortex/
├── app.py                  # backend Flask (serve o front + API de projetos)
├── templates/index.html    # SPA (5 etapas)
├── static/
│   ├── css/styles.css      # tema escuro próprio (sem framework)
│   └── js/
│       ├── app.js          # estado, uploads, formulário, narração TTS, projetos
│       ├── scriptgen.js    # motor de roteiro PT-BR (tons, minutagem, cenas)
│       ├── staging.js      # staging virtual em canvas (4 estilos × 7 ambientes)
│       ├── tour.js         # viewer com panorâmica 360° simulada
│       ├── video.js        # render Ken Burns + MediaRecorder + trilha WebAudio + SRT
│       └── demo.js         # fotos demo procedurais
│   └── assets/             # cutouts de mobiliário (PNG com alpha) + raw/ originais
├── tools/make_assets.py    # recorte fundo branco → PNG com alpha
├── data/                   # projetos salvos (projects.json)
└── tests/                  # testes da API e dos assets (pytest)
```

### API

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/api/health` | status |
| `GET` | `/api/projects` | lista projetos (resumido) |
| `POST` | `/api/projects` | cria projeto |
| `GET` | `/api/projects/<id>` | recupera projeto completo |
| `PUT` | `/api/projects/<id>` | atualiza projeto |
| `DELETE` | `/api/projects/<id>` | exclui projeto |

## 🪑 Assets de mobiliário (staging fotográfico)

O staging compõe **cutouts fotográficos** (PNG com alpha) dentro do panorama. Se um
PNG não existir, o código cai no **fallback procedural** — os assets são um upgrade
visual, não um requisito.

Os cutouts versionados em `static/assets/` são gerados a partir das fotos de produto
em fundo branco guardadas em `static/assets/raw/`:

```bash
python tools/make_assets.py --preview   # recorta tudo + gera a prancha de conferência
python tools/make_assets.py --only vase-decor
```

O pipeline estima a cor do fundo pela moldura da imagem, converte o desvio em alpha
com rampa suave, remove ilhas soltas, desfaz o *spill* branco das bordas e recorta no
conteúdo. Dois ajustes existem porque só aparecem na prática:

| Ajuste | Para quê | Onde é usado |
|--------|----------|--------------|
| `--kill-shadows` | derruba a **sombra projetada** no chão (borrão cinza que denuncia a colagem) | `vase-decor` |
| `--fill-holes` | tapa **buraco fechado** (o passe-partout branco de um quadro virava janela transparente) | `wall-art` |

> **Confira olhando.** A prancha `static/assets/_preview.png` mostra cada cutout sobre
> três fundos — cinza, madeira e **escuro**. Os fundos claros ficam de fora de
> propósito: fundo branco esconde exatamente o defeito que se quer enxergar (halo
> claro na borda). Os testes de `tests/test_assets.py` travam o resto (cantos
> transparentes, nada de fundo colado na borda, cobertura plausível).

## 🧪 Testes

```bash
pytest -q
```

## 💡 Notas

- O vídeo sai em **.webm** (VP8/VP9 + Opus), que abre no Chrome/Edge e no WhatsApp Web. Para **MP4**, arraste o arquivo no CapCut/CloudConvert ou rode `ffmpeg -i tour.webm tour.mp4`.
- A narração “Ouvir” usa a voz PT-BR do próprio navegador (Speech Synthesis).
- O staging virtual é uma **simulação ilustrativa** (renderizada em canvas) para transmitir a sensação de ambiente mobiliado — o app sinaliza isso na tela com o selo “✨ Simulação de ambiente mobiliado”.
