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
│   └── assets/
│       ├── layouts.json    # layout do staging fotográfico (fonte de verdade)
│       ├── *.png           # cutouts de mobiliário (PNG com alpha)
│       └── raw/            # fotos de produto originais (fundo branco)
├── tools/
│   ├── make_assets.py      # recorte fundo branco → PNG com alpha
│   └── preview_staging.py  # conferidor do layout em PIL (sem navegador)
├── data/                   # projetos salvos (projects.json)
└── tests/                  # API, assets, layout e geometria (pytest)
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

## 🪑 Staging fotográfico

O staging tem **duas camadas**, decididas automaticamente a cada quadro:

| Camada | Quando entra | O que desenha |
|--------|--------------|----------------|
| **Fotográfica** | quando o `layouts.json` e os cutouts do ambiente carregaram | **cutouts fotográficos** (PNG com alpha) compostos no ambiente, com sombra de contato e ajuste tonal por estilo |
| **Procedural** | sempre que a fotográfica não está pronta | mobiliário vetorial desenhado no canvas (o comportamento original, sem mudanças) |

Nada quebra se um PNG faltar: o ambiente que precisa dele volta inteiro para a
camada procedural, e o selo na tela diz qual das duas está ativa
("✨ Staging: mobília fotográfica" × "✨ Simulação de ambiente mobiliado").

O layout é declarativo em `static/assets/layouts.json` — **coordenda nenhuma mora no
JS**. Pontos que valem saber antes de mexer:

- **As coordenadas são frações da FOTO, não do canvas.** A mobília é dimensionada em
  múltiplos da altura da foto, então ela **anda junto com o ambiente** quando a
  panorâmica se move ou o zoom muda. É isso que evita o móvel "deslizando" por cima
  do chão durante o giro — e é a razão de `VVStaging.draw()` receber `scene`.
- **`h` é a altura do objeto** (fração da altura da foto) e a **largura sai do
  aspecto real do PNG**. Nunca há duas medidas para manter em sincronia: trocar o
  cutout por um mais largo ajusta a largura sozinho.
- **`anchor` descreve o ASSET**, não o uso: `floor`/`surface` posicionam por
  `bottom`, `wall`/`ceiling` por `top`. Um quadro pendurado usa `top` (e é por isso
  que o merge do anchor acontece em `placementsFor` — sem ele o quadro é pintado no
  chão e some atrás do sofá).
- **`depth` (0 = fundo, 1 = câmera)** ordena o desenho e modula a sombra e o
  desfoque atmosférico dos objetos mais distantes.
- **Estilos** são um ajuste tonal (`filter` + `shadow`) sobre o *mesmo* móvel, então
  um sofá só precisa existir uma vez para os 4 estilos.

Os cutouts vêm das fotos de produto em fundo branco guardadas em `static/assets/raw/`
e são recortados por `tools/make_assets.py`:

```bash
python tools/make_assets.py --preview   # recorta tudo + prancha de conferência
python tools/make_assets.py --only vase-decor
```

O pipeline estima a cor do fundo pela moldura da imagem, converte o desvio em alpha
com rampa suave, remove ilhas soltas, desfaz o *spill* branco das bordas e recorta no
conteúdo. Dois ajustes existem porque só aparecem na prática:

| Ajuste | Para quê | Onde é usado |
|--------|----------|--------------|
| `--kill-shadows` | derruba a **sombra projetada** no chão (o borrão cinza que denuncia a colagem) | sofa, bed, vase-decor, table-lamp, dining-set, nightstand, plant |
| `--fill-holes` | tapa **buraco fechado** (o passe-partout branco de um quadro virava janela transparente) | wall-art |

A supressão de sombra é conservadora de propósito: age só na **faixa de baixo do
objeto**, em pixel **neutro** (croma < 8, contra 26 no corpo do sofá) e **claro**. Os
dois casos que quebram a abordagem ingênua ("pixel claro e neutro") ficam de fora:
o **edredom branco da cama** (claro e neutro, mas no meio do objeto) e os **braços do
sofá** (na faixa de baixo, mas com croma de tecido). Cada asset tem `band`/`tol`
medidos em `PRESETS`, e o pipeline avisa quando a supressão remove alpha demais —
sinal de que está comendo o móvel, não a sombra.

> **Confira olhando.** `tools/preview_staging.py` reimplementa a mesma geometria em
> PIL e compõe os ambientes sobre um cenário sintético com **linha de piso e
> rodapé** — as duas referências que dizem se o móvel está plantado no chão:
>
> ```bash
> python tools/preview_staging.py --tracking
> # static/assets/_staging_preview.png   (grades de ambientes × estilos)
> # static/assets/_staging_tracking.png  (arrasto de panorâmica: móvel deve ficar fixo no piso)
> ```
>
> A prancha dos cutouts (`_preview.png`) usa fundos cinza, madeira e **escuro** de
> propósito: fundo branco esconde exatamente o defeito que se quer enxergar (halo
> claro na borda). Os testes de `tests/test_assets.py` travam o resto (cantos
> transparentes, nada de fundo colado na borda, sombra residual na base).

### Por que a geometria é testada duas vezes

O sandbox não tem navegador, então **a única forma de olhar o staging é o preview em
PIL**. Se a conta do PIL divergir da do `staging.js`, o preview vira ficção — eu
aprovo um layout que no navegador aparece diferente. Por isso
`tests/test_staging_geometry.py` roda as funções puras do `staging.js` **no node** e
compara com a implementação Python para uma matriz de casos (zoom do tour,
deslocamentos de panorâmica, foto mais larga que o canvas, os 4 anchors), e ainda
exercita `preload()`/`placementsFor()` com `fetch` e `Image` dublados. Sem node
instalado, esses testes são pulados.

Junto com `tests/test_staging_layout.py` (limites de coordenada, âncora por asset,
ordem de profundidade, ambientes cobertos) e `tests/test_assets.py` (validade dos
cutouts), são os testes que substituem o olho humano no que dá para automatizar.

Os cutouts versionados em `static/assets/` são gerados a partir das fotos de produto
em fundo branco guardadas em `static/assets/raw/`:

```bash
python tools/make_assets.py --preview   # recorta tudo + gera a prancha de conferência
python tools/make_assets.py --only vase-decor
```

## 🧪 Testes

```bash
pytest -q                       # API + assets + layout + geometria do staging
node --check static/js/*.js     # sintaxe do front
```

## 💡 Notas

- O vídeo sai em **.webm** (VP8/VP9 + Opus), que abre no Chrome/Edge e no WhatsApp Web. Para **MP4**, arraste o arquivo no CapCut/CloudConvert ou rode `ffmpeg -i tour.webm tour.mp4`.
- A narração “Ouvir” usa a voz PT-BR do próprio navegador (Speech Synthesis).
- O staging virtual é uma **simulação ilustrativa** (renderizada em canvas) para transmitir a sensação de ambiente mobiliado — o app sinaliza isso na tela com o selo “✨ Simulação de ambiente mobiliado”.
