# Playbook: Documentário Científico Procedural em Vídeo

> **Para o agente de IA que receber esta tarefa.** Este documento descreve um pipeline
> completo, já testado em produção, para gerar um documentário narrado de 10 a 15 minutos
> inteiramente por código — vídeo 1080p, narração em português, trilha sonora original e
> legendas — usando apenas Python, NumPy, SciPy, Pillow e ffmpeg, sem modelos de vídeo,
> sem bancos de imagens e sem marcas d'água.
>
> O projeto original tratava do Problema de Navier-Stokes. **O assunto é uma variável.**
> Leia as seções 1 e 2, preencha o bloco de configuração, e siga as fases na ordem.
>
> **Princípio de recursos:** nada de terceiros entra no produto final — sem imagens de
> banco, sem vídeo de arquivo, sem trilha licenciada, sem modelo de imagem ou vídeo.
> Só matemática, ffmpeg, uma fonte livre e TTS. O inventário completo está na seção 2.

---

## 0. Entradas da tarefa (variáveis)

O usuário fornece, no mínimo:

| Variável | Descrição | Exemplo |
|---|---|---|
| `ASSUNTO` | Tema central do documentário | "A Hipótese de Riemann" |
| `ROTEIRO_INICIAL` | Estrutura em capítulos, com o que deve aparecer e ser dito | ver seção 1.2 |
| `IDIOMA` | BCP-47 da narração | `pt-BR` |
| `PREMISSA` | Tese/enquadramento que deve ser repetido (opcional, mas comum) | "Continua em aberto" |
| `ESTILO` | Paleta e direção de arte | "fundo escuro, neon azul e laranja" |

Se qualquer um desses estiver ausente ou ambíguo **de um jeito que mude o resultado**,
pergunte antes de começar. Não pergunte o que dá para inferir.

### 0.1 Definição de pronto

- [ ] N capítulos em MP4 1080p 24 fps, cada um com narração + trilha embutidas
- [ ] Arquivo `.srt` com legendas do filme inteiro
- [ ] `narracao.txt` com o roteiro final falado
- [ ] Código-fonte reutilizável em `nsfilm/` (ou nome equivalente)
- [ ] Nenhum texto cortado nas bordas, nenhuma sobreposição de rótulos
- [ ] A premissa aparece na abertura, no meio e na conclusão (se houver premissa)

---

## 1. Planejamento

### 1.1 Regra de ouro da duração

**A narração dita o tempo, não o contrário.** Meça primeiro, planeje depois.

- Português brasileiro falado: ~800–900 caracteres por minuto.
- Um bloco de narração de ~1100 caracteres ≈ 55–65 segundos.
- A duração de cada cena = duração do áudio + 8 a 15 s de respiro (abertura visual
  antes da fala, mais um fecho depois).

> **Aviso honesto ao usuário:** se ele pedir 30 minutos, diga na hora que isso exige
> ~2,5× mais texto do que a estrutura sugerida costuma render, e ofereça as duas opções.
> Não entregue 12 minutos silenciosamente quando pediram 30 — diga o que foi entregue
> e o que faltaria para chegar lá. No projeto original entregamos 11:48 para um pedido
> de 30 min e explicamos a diferença; isso foi aceito, mas só porque foi declarado.

### 1.2 Formato do roteiro por capítulo

Para cada capítulo, defina quatro coisas:

```
CAPÍTULO N — <título curto>
VISUAL:    o que a animação mostra, em uma frase concreta e renderizável
TEXTO:     as palavras que aparecem na tela (4 a 8 cartelas curtas, caixa alta)
EQUAÇÕES:  LaTeX, se houver
NARRAÇÃO:  ~1100 caracteres, texto corrido, pronto para TTS
```

"Renderizável" é a palavra-chave em VISUAL. "Um vórtice sendo esticado" é renderizável.
"A angústia do matemático" não é. Traduza conceitos abstratos em **movimento, escala,
corrida entre duas forças, ciclo que se realimenta, antes e depois**.

### 1.3 Arquétipos visuais reutilizáveis

Estes nove padrões cobrem quase qualquer assunto científico. Todos estão implementados
no código de referência e são adaptáveis trocando parâmetros e cores:

| Arquétipo | Serve para | Implementação |
|---|---|---|
| Espiral logarítmica | furacão, galáxia, redemoinho, qualquer rotação diferencial | `hurricane_layer`, `galaxy_layer` |
| Tubo/filamento torcido | concentração, intensificação, afinamento | `vortex_tube` |
| Caixa com linhas de corrente | campo vetorial 3D, sistema fechado, câmera orbital | `scene2` |
| Disco com sombra central | buraco negro, acreção, atrator | `accretion_disk` |
| Ciclo de 3 nós | realimentação, recursividade, feedback | `scene7` (primeira metade) |
| Duas barras em corrida | competição entre forças, "quem vence?" | `scene7` (segunda metade) |
| Dois gráficos empilhados | uma grandeza explode, outra permanece finita | `scene6` |
| Placa com selo vermelho | desmentido, alerta, "FALSO" | `scene3` |
| Grade de partículas perturbada | repouso → perturbação → estrutura | `scene5` |

---

## 2. Recursos externos: o que foi usado, como e por quê

Esta seção existe para deixar explícito **de onde vem cada coisa**. O princípio que guiou
todas as escolhas: *nenhum recurso de terceiros entra no produto final*. Nenhuma imagem de
banco, nenhum vídeo de arquivo, nenhuma trilha licenciada, nenhuma fonte proprietária,
nenhuma chamada a modelo de imagem ou vídeo. Tudo o que aparece na tela é gerado por
código a partir de primitivas matemáticas, e tudo o que se ouve é sintetizado ou falado
por TTS. Isso garante ausência de marca d'água, ausência de conflito de licença e
reprodutibilidade total.

### 2.1 Panorama

| Recurso | Papel | Origem | Alternativa se faltar |
|---|---|---|---|
| Python 3.13 | linguagem base | pré-instalado | qualquer 3.10+ |
| NumPy 2.3 | toda a matemática de imagem e áudio | pré-instalado | obrigatório |
| SciPy 1.17 | `gaussian_filter`, filtros Butterworth | pré-instalado | obrigatório na prática |
| Pillow 12.3 | desenho de texto, leitura/escrita de JPEG | pré-instalado | obrigatório |
| matplotlib 3.10 | rasterizar equações LaTeX | pré-instalado | escrever equações à mão em Unicode |
| imageio-ffmpeg 0.6 | fornece o binário do ffmpeg | **`pip install`** | ffmpeg do sistema, se houver |
| ffmpeg 7.0.2 | encoding H.264, filtros de áudio, concat | vem dentro do pacote acima | obrigatório |
| DejaVu Sans | toda a tipografia | fonte do sistema | Liberation, Noto |
| Ferramenta de TTS | narração em português | plataforma do agente | qualquer TTS com PT-BR |

### 2.2 Bibliotecas Python — por que cada uma

**NumPy** é o motor real do projeto. Cada frame é um array `(H, W, 3)` em `float32`, e cada
efeito é aritmética vetorizada sobre ele. Não há laço em Python sobre pixels em lugar
nenhum — seria centenas de vezes mais lento. As partículas também são arrays: posição
`(N, 3)`, cor `(N, 3)`, intensidade `(N,)`, todas manipuladas de uma vez. O único ponto
onde há indexação dispersa é o `np.add.at` do `splat`, e ele é o gargalo justamente por
isso.

**SciPy** entra por duas funções:

- `scipy.ndimage.gaussian_filter` — é o que transforma pontos em luz. Usado no
  `finish_parts` (partícula vira campo contínuo), no `bloom` (halo das altas luzes) e no
  amaciamento de linhas finas. Sem ele, o vídeo inteiro pareceria ruído branco.
- `scipy.signal.butter` + `sosfilt` — filtros passa-baixa e passa-alta da síntese sonora.
  É o que dá aos pads o caráter "analógico" e mantém os graves limpos.

**Pillow** faz só o que NumPy não faz bem: rasterizar texto com uma fonte TrueType.
O resultado volta imediatamente para NumPy como array. Também é o formato de saída dos
*contact sheets* de inspeção.

**matplotlib** é usado de um jeito bastante específico e não óbvio: **apenas como
renderizador de LaTeX**. Nenhum gráfico do matplotlib aparece no vídeo — os gráficos da
cena 6 são desenhados com `splat`, como todo o resto. O que se aproveita é o mecanismo
`mathtext`, que converte `$\frac{\partial u}{\partial t}$` em pixels:

```python
fig = plt.figure(figsize=(0.01, 0.01))
fig.text(0, 0, tex, fontsize=fontsize, color=color)
fig.savefig(buf, dpi=220, transparent=True, bbox_inches="tight", pad_inches=0.06)
alpha = np.asarray(Image.open(buf).convert("RGBA"), np.float32)[..., 3]   # só o canal alpha
```

Guardamos **somente o canal alpha**. A cor é aplicada depois, no momento de compor, o que
permite colorir a mesma equação de branco ou ciano e aplicar o *wipe* de revelação sem
re-renderizar. Todas as máscaras são cacheadas em `_eqcache`.

> Por que não desenhar as equações à mão? Porque `∂u/∂t + (u·∇)u = −∇p + νΔu` com frações
> empilhadas e espaçamento matemático correto é trabalhoso e fica visivelmente amador em
> Unicode puro. O mathtext resolve com uma linha e tem aparência de publicação.

### 2.3 ffmpeg — o recurso externo mais importante

**Não vem instalado no sandbox.** É preciso instalar em toda sessão:

```bash
pip install imageio-ffmpeg
python3 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
# /usr/local/.../imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2
```

Usamos o pacote `imageio-ffmpeg` apenas como **veículo de distribuição de um binário
estático** — nenhuma função da API do imageio é chamada. Pegamos o caminho do executável
e conversamos com ele por `subprocess`. É a forma mais confiável de ter ffmpeg num
ambiente onde não há gerenciador de pacotes do sistema disponível.

O ffmpeg cumpre **cinco papéis distintos**, e vale entender cada um:

1. **Encoder de vídeo.** Os frames nunca tocam o disco como imagens. O render escreve
   bytes RGB crus direto no `stdin` do ffmpeg, que codifica em H.264 em tempo real:
   ```python
   cmd = [ff, "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", "24", "-i", "-", ...]
   proc.stdin.write(to_bytes(img))
   ```
   Gravar 17 000 PNGs e depois juntá-los seria mais lento e encheria o disco.

2. **Escalador.** O filtro `scale=1920:1080:flags=lanczos` faz o upscale de 1440×808 para
   1080p dentro do próprio encoder. Essa única linha é responsável por cortar o tempo de
   render pela metade — é mais barato o ffmpeg escalar em C do que nós renderizarmos 78%
   mais pixels em Python.

3. **Medidor de duração.** As durações reais dos áudios de TTS saem do `stderr` do ffmpeg
   e são o que define o `PLAN` de tempos das cenas.

4. **Mixador de áudio.** Aqui ele substitui código nosso que falhava. O `adelay` posiciona
   cada bloco de narração no tempo certo, o `amix` junta, o `sidechaincompress` faz a
   música abaixar sob a voz, o `alimiter` controla os picos e o `afade` fecha. Tudo isso
   em uma chamada, com uso de memória constante — enquanto a versão equivalente em NumPy
   foi morta pelo OOM killer duas vezes.

5. **Multiplexador e concatenador.** Junta vídeo e áudio com `-c copy` (sem recodificar),
   corta o trecho de trilha de cada capítulo com `-ss`/`-t`, e concatena pedaços de uma
   mesma cena com o demuxer `concat`. Também extrai frames de verificação do MP4 pronto.

### 2.4 Fontes

O sandbox só tem a família **DejaVu** (e Noto CJK, irrelevante aqui):

```
/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf     -> títulos e cartelas
/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf          -> textos de apoio
/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf      -> elementos técnicos, "RUMOR"
```

DejaVu Sans Bold funciona bem para este estilo: é geométrica, tem boa cobertura de
acentuação portuguesa e os caracteres gregos (`ω`, `ν`, `Δ`, `∇`, `∂`) necessários fora
das equações LaTeX. Verifique com `fc-list` antes de assumir qualquer outra. **Não tente
baixar fontes** — além do risco de licença, o sandbox pode não ter rede na hora do render.

### 2.5 Ferramenta de TTS

O único recurso externo que não é determinístico. Duas orientações que importam:

- **Audicione antes de gerar tudo.** A escolha de voz é do usuário; gerar 10 minutos de
  narração com uma voz que ele vai rejeitar desperdiça o trabalho inteiro. Use como texto
  de audição um trecho real do roteiro — funciona como prévia do produto.
- **Gere os blocos em paralelo.** São independentes; emitir as 10 chamadas numa única
  resposta leva o mesmo tempo que uma.

O TTS produz MP3. Tudo a partir daí é ffmpeg.

### 2.6 Recursos deliberadamente NÃO usados

| Não usado | Por quê |
|---|---|
| Modelos de geração de imagem/vídeo | marcas d'água, inconsistência entre frames, impossibilidade de sincronizar com narração, custo |
| Imagens de arquivo (furacões, buracos negros reais) | licenciamento, estética inconsistente com o resto, o pedido era explicitamente "sem marcas d'água" |
| Manim | pesado, exige LaTeX completo instalado; replicamos o *visual* com mathtext + wipe |
| OpenCV | nada que ele faça aqui que `scipy.ndimage` não faça |
| MoviePy | abstração desnecessária sobre o ffmpeg, e mais consumo de memória |
| Bibliotecas de música (pretty_midi, fluidsynth) | exigiriam SoundFonts externos; síntese em NumPy dá controle total e zero dependência |
| Blender / renderizador 3D | indisponível, e a projeção de 15 linhas em `core.py` basta para nuvens de pontos |
| Rede durante o render | pode não estar disponível; todo o pipeline roda offline depois do `pip install` |

Em resumo: a lista de dependências é curta de propósito. Quanto menos recursos externos,
menos pontos de falha em um ambiente que reinicia entre mensagens.

### 2.7 Versões exatas da execução de referência

Verificadas no sandbox em que o documentário de Navier-Stokes foi produzido:

```
python 3.13.14
numpy 2.3.5
scipy 1.17.1
pillow 12.3.0
matplotlib 3.10.9
imageio_ffmpeg 0.6.0
ffmpeg 7.0.2-static (johnvansickle.com/ffmpeg) — binário embarcado no pacote acima
fontes: DejaVu (Sans, Sans-Bold, Sans-Mono, Serif) + Noto CJK
```

Nada aqui depende de versão específica, com uma exceção já documentada: em matplotlib
recente `mathtext.MathTextParser("bitmap")` foi removido — use a rota `fig.text` +
`savefig` da seção 5.7.

### 2.8 Bootstrap: primeira coisa a rodar em cada sessão

```bash
pip install imageio-ffmpeg
python3 - <<'EOF'
import numpy, scipy, PIL, matplotlib, imageio_ffmpeg, subprocess, glob
print("numpy", numpy.__version__, "| scipy", scipy.__version__,
      "| pillow", PIL.__version__, "| mpl", matplotlib.__version__)
ff = imageio_ffmpeg.get_ffmpeg_exe()
print(subprocess.run([ff, "-version"], capture_output=True, text=True).stdout.split("\n")[0])
print("fontes:", glob.glob("/usr/share/fonts/truetype/dejavu/*.ttf"))
EOF
```

Se `imageio-ffmpeg` falhar por ausência de rede, procure um ffmpeg do sistema com
`which ffmpeg`. Sem ffmpeg, **nada** deste pipeline funciona — resolva isso antes de
escrever qualquer linha de cena.

---

## 3. Ambiente e restrições do sandbox

### 3.1 Verificação inicial (rode sempre primeiro)

```bash
nproc                                    # tipicamente 2 núcleos
free -m | head -2                        # tipicamente ~2 GB de RAM
df -h /home/user | tail -1               # tipicamente ~20 GB livres
python3 -c "import numpy, scipy, PIL; print(numpy.__version__, scipy.__version__, PIL.__version__)"
pip install imageio-ffmpeg               # ffmpeg NÃO vem instalado
python3 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"
fc-list | head                           # DejaVu costuma ser a única família disponível
```

### 3.2 As três restrições que vão te morder

Estas custaram horas no projeto original. Leia com atenção.

**(a) O sandbox reinicia entre mensagens.** Pacotes instalados via `pip` **não persistem**.
Processos em background **são mortos**. Reinstale `imageio-ffmpeg` no início de cada
mensagem em que for usar ffmpeg, e trate todo render longo como interrompível.

**(b) O snapshot do workspace tem teto de tamanho (~128 MB).** Arquivos grandes são
**descartados silenciosamente** ao fim do turno. No projeto original perdemos um MP4 de
629 MB e, depois, uma pasta inteira de capítulos, duas vezes. Consequências práticas:

- Nunca deixe o workspace passar de ~90 MB ao fim de um turno.
- Apague renders intermediários assim que consumi-los.
- **Entregue em capítulos de 5 a 30 MB, um por vez**, e peça ao usuário para baixar
  antes de gerar os próximos.
- Prefira a raiz (`/home/user/arquivo.mp4`) a subpastas — o usuário acha mais fácil.

**(c) ~2 GB de RAM.** Um array float32 de 1920×1080×3 são 25 MB; uma dúzia de temporários
simultâneos estoura. Processamento de áudio de 12 minutos em float64 estoura. Soluções na
seções 6.3 e 7.3.

### 3.3 Estratégia de render resiliente

```python
# Sempre: marcador .ok por capítulo, para permitir retomada
done = f"{out_dir}/part{i+1:02d}.ok"
if os.path.exists(done):
    print("skip"); continue
# ... renderiza ...
open(done, "w").write("1")
```

Rode **dois processos em paralelo** (um por núcleo), com listas de índices
intercaladas por custo — não sequenciais:

```bash
python3 render.py 0 1 2 3 4 &   # ruim: desbalanceado
python3 render.py 2 4 1 &        # bom: mistura caras e baratas
python3 render.py 9 3 8 &
```

Para uma cena muito cara, divida em metades por intervalo de frames e concatene depois
(veja `chunk.py`, seção 10.4). Cuidado: cenas com estado de simulação (partículas) precisam
de um *fast-forward* barato que avance só a física, sem renderizar.

---

## 4. Arquitetura do código

```
nsfilm/
├── core.py        # canvas, splat, bloom, grade, texto, equações, projeção 3D
├── fluid.py       # campos procedurais (curl-noise, swirl) — trocar por domínio do assunto
├── scenes_a.py    # cenas 1–5
├── scenes_b.py    # cenas 6–10
├── render.py      # PLAN (cena, duração) + loop de encoding
├── chunk.py       # render parcial por intervalo de frames (cenas caras)
├── music.py       # síntese: pads, drones, arpejos, pulso, riser
├── make_music.py  # composição por seções -> trilha.m4a
├── mixdown.py     # posicionamento da narração (só cálculo de offsets)
├── make_srt.py    # legendas a partir de narracao.txt + durações reais
└── publish.py     # corta o áudio por capítulo e nomeia os arquivos finais
```

Toda cena tem a mesma assinatura, o que torna o `PLAN` trivial:

```python
def sceneN(t, T):
    """t = segundos desde o início da cena; T = duração total. Retorna (H,W,3) float32 em [0,1]."""
    p = t / T          # progresso normalizado, use-o para TODO o timing
    c = dark_bg(t)
    # ... camadas ...
    c = bloom(c, 0.55, 15)
    return grade(c, 1.03, 0.010, ab=1.1, t=t)
```

---

## 5. Motor de render (`core.py`)

### 5.1 Resolução: renderize menor, entregue 1080p

**Decisão crítica de performance.** Renderizar nativo em 1920×1080 custou ~230 min de CPU.
Renderizar em **1440×808** e deixar o ffmpeg escalar para 1920×1080 com Lanczos custou
~98 min, com diferença visual desprezível para conteúdo difuso e brilhante.

```python
W, H = 1440, 808     # H múltiplo de 8 — 810 quebra os reshapes de downsample!
FPS = 24
```

E no encoder: `-vf scale=1920:1080:flags=lanczos`.

> Armadilha real: usei 810 e o `_down4` quebrou com
> `cannot reshape array of size 3499200`. Use múltiplos de 8 em ambas as dimensões.

### 5.2 Acumulação de partículas (`splat`)

O núcleo de tudo. Espalha N partículas num canvas com interpolação bilinear:

```python
def splat(canvas, x, y, inten, color, size=1):
    """Coordenadas em pixels de TELA; escala sozinho se o canvas for reduzido."""
    hh, ww_, _ = canvas.shape
    sc = ww_ / W
    if sc != 1.0:
        x = x * sc; y = y * sc
    m = np.isfinite(x) & np.isfinite(y) & (x >= 1) & (x < ww_-2) & (y >= 1) & (y < hh-2)
    ...
    for dx, dy, wt in ((0,0,(1-fx)*(1-fy)), (1,0,fx*(1-fy)), (0,1,(1-fx)*fy), (1,1,fx*fy)):
        np.add.at(canvas[..., ch], (y0+dy, x0+dx), (w*wt) * col[...])
```

> Tentei substituir `np.add.at` por `np.bincount` esperando ganho — **ficou 2× mais lento**
> neste caso. Não repita a otimização. O ganho real veio de (i) reduzir a resolução base,
> (ii) acumular partículas em buffers de meia resolução, (iii) cachear fundos estáticos.

### 5.3 De nuvem esparsa a campo contínuo (`finish_parts`)

Partículas cruas parecem poeira. Este passo é o que transforma pontos em *fluido luminoso*:

```python
def finish_parts(c, gain=9.0, soft=1.15, soft2=3.4, mix2=0.45):
    """Borrão fino + borrão largo (em 1/2 res) + ganho. Devolve sempre em resolução total."""
    div = W // c.shape[1]
    a = gaussian_filter(c, (soft/div, soft/div, 0), mode="nearest")
    b = _upN(gaussian_filter(c[::2, ::2], (s2, s2, 0), mode="nearest"), 2)
    a = (a + mix2 * b) * (gain * div * div * 0.25 if div > 1 else gain)
    return _upN(a, div) if div > 1 else a
```

Use buffers reduzidos para partículas e componha em resolução total:

```python
pc = pbuf(2)                       # canvas H/2 × W/2
splat(pc, x, y, w, col)            # coordenadas ainda em pixels de tela
c += finish_parts(pc, gain=8.0)    # volta em resolução total
```

**Calibração de brilho:** comece com `gain` entre 6 e 10. Se o resultado parecer poeira
escura, o problema quase nunca é o bloom — é densidade de partículas baixa demais ou
`gain` baixo demais. Densidades que funcionaram: 110k–170k partículas para discos e
espirais que ocupam a tela; 5k partículas × 12–18 passos de *streamline* para campos
vetoriais; 45k para tornados e tubos.

### 5.4 Bloom e correção de cor

```python
def bloom(canvas, amount=0.55, radius=14, thr=0.32):
    small = _down4(canvas)                       # 1/4 de resolução: 16× mais barato
    m = np.clip(small.max(-1) - thr, 0, None)[..., None]
    src = np.minimum(small, 4.0) * (m > 0)
    g = amount * gaussian_filter(src, r) + amount*0.65 * gaussian_filter(src, r*3.2)
    return canvas + _upN(gaussian_filter(g, 0.7), 4)

def grade(c, exposure=1.0, grain=0.010, vignette=True, ab=0.0, t=0.0):
    c *= exposure                                 # in-place: economiza RAM
    c *= _VIG[..., None]                          # vinheta pré-computada
    if ab > 0: c = chroma_ab(c, ab)               # aberração cromática: 1–1.6 px
    c = (c*(2.51*c+0.03)) / (c*(2.43*c+0.59)+0.14)  # tone map ACES filmic
    c += grain * np.roll(_GRAIN, sh)[..., None]   # grão rolado ≠ grão novo por frame
    return np.clip(c, 0, 1, out=c)
```

O tone map ACES é o que dá aparência "cinematográfica" — sem ele, os brancos estouram
chapados. O grão deve ser **um único array pré-gerado, rolado** a cada frame; gerar ruído
novo por frame é caro e cintila demais.

### 5.5 Cache agressivo de elementos estáticos

```python
_bgc = {}       # gradiente de fundo por (tint, level)
_SFC = {}       # campo de estrelas por seed
_EL  = {}       # limbo do planeta
_eqcache = {}   # máscaras alpha de equações LaTeX
```

Qualquer coisa que não dependa de `t` deve ser calculada uma vez. Isso sozinho tirou
~30% do tempo de render.

### 5.6 Tipografia

```python
FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
F_BOLD, F_REG, F_MONO = FONT_DIR+"DejaVuSans-Bold.ttf", ..., ...

def text_layer(items):
    """items: [{text, xy, size, color, alpha, anchor, font, spacing, align}]"""
    img = Image.new("RGB", (W, H), (0,0,0))
    d = ImageDraw.Draw(img)
    for it in items:
        col = np.asarray(it["color"]) * it["alpha"]     # alpha via multiplicação de cor
        d.text(it["xy"], it["text"], font=..., fill=rgb, anchor=it.get("anchor","mm"))
    return np.asarray(img, np.float32) / 255.0
```

O texto é desenhado em uma camada preta e **somado** ao canvas — assim ele recebe bloom
e ganha o brilho neon naturalmente, sem compositing alpha.

> **Armadilha de tipografia que custou um re-render:** eu fixei tamanhos de fonte pensando
> em 1920 px de largura, mas o render base é 1440. Tentei "corrigir" escalando as fontes
> por `W/1920` — **errado**: com a fonte proporcional, o texto que já cabia passou a ter
> a mesma proporção, e a cartela final continuou cortando. A correção certa foi
> **quebrar a linha do texto longo** (`"O ESTIRAMENTO VENCE\nA VISCOSIDADE?"`) e manter os
> tamanhos absolutos. Regra prática: nenhuma linha deve passar de ~26 caracteres em
> corpo 60+; se passar, quebre em duas.

Verifique **sempre** um frame de cada cartela de texto antes do render final.

### 5.7 Equações via matplotlib mathtext

```python
def eq_image(tex, fontsize=42, color="white"):
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, tex, fontsize=fontsize, color=color)
    fig.savefig(buf, dpi=220, format="png", transparent=True, bbox_inches="tight", pad_inches=0.06)
    return np.asarray(Image.open(buf).convert("RGBA"), np.float32)[..., 3]   # só o alpha
```

> `mathtext.MathTextParser("bitmap")` **não existe mais** no matplotlib recente — dá
> `ValueError: 'bitmap' is not a valid value`. Use a rota `figure.text` + `savefig`
> mostrada acima.

A máscara alpha é colada com cor neon e um *wipe* horizontal, que dá o efeito "escrita
surgindo" estilo Manim:

```python
paste_alpha(c, eq1, W/2, H*0.40, WHITE, gain=1.15*a,
            reveal=smoothstep(0.54, 0.70, p))    # reveal = wipe 0..1
```

### 5.8 Projeção 3D e câmera orbital

```python
def project(P, ang, elev, radius, fov=1500.0):
    """P: (N,3) -> (sx, sy, z_camera). Rotação em Y, depois elevação, depois perspectiva."""
    ca, sa = np.cos(ang), np.sin(ang); ce, se = np.cos(elev), np.sin(elev)
    xr =  ca*P[:,0] + sa*P[:,2]
    zr = -sa*P[:,0] + ca*P[:,2]
    yr = ce*P[:,1] - se*zr
    zc = se*P[:,1] + ce*zr + radius
    return W/2 + fov*xr/zc, H/2 - fov*yr/zc, zc
```

Órbita lenta: `ang = 0.35 + 0.115*t`. A intensidade de cada partícula deve cair com a
profundidade — `(4.6/zc)**1.8` — senão o volume parece chapado.

---

## 6. Áudio

### 6.1 Narração (TTS)

1. **Audicione a voz primeiro**, com um trecho real do roteiro (~15 s, 30–45 palavras).
   Isso serve de prévia para o usuário e evita regravar tudo depois.
2. Divida a narração em **um bloco por capítulo**, cada um ≤ 1500 caracteres.
3. **Gere todos os blocos em paralelo, numa única resposta** — são independentes.
4. Meça as durações reais com ffmpeg; elas definem o `PLAN`.

```python
m = re.search(r'Duration: (\d+):(\d+):([\d.]+)', stderr)
```

Escreva o texto para ser **falado**: frases curtas, sem parênteses aninhados, números por
extenso quando ajudar ("cento e oitenta anos"), símbolos verbalizados
("ômega igual a nabla vetorial u").

### 6.2 Trilha original por síntese

Nada de biblioteca de música. Sintetize com NumPy:

| Elemento | Função | Papel |
|---|---|---|
| Pad | 3 serras levemente desafinadas + sub, filtro passa-baixa | base harmônica |
| Sub-drone | seno fundamental + oitava, LFO lento | peso, tensão |
| Arpejo | seno+serra com envelope exponencial, em colcheias | movimento |
| Pulso | seno com pitch-drop exponencial (58→34 Hz) | batida suave |
| Riser | frequência exponencial + ruído filtrado crescente | transição |
| Impacto | seno grave + ruído, decaimento rápido | pontuação dramática |
| Wash | ruído passa-baixa com LFO | textura |

Estruture por seções com uma **curva de intensidade** que acompanha a narrativa:

```python
SECT = [
    (0,    66, "Dm", 0.30, 0),     # abertura: só pad e drone
    (142,  66, "Gm", 0.45, 72),    # tensão entra
    (411,  81, "A",  0.72, 84),    # clímax: pulso forte, contra-melodia
    (640,  68, "D",  0.85, 72),    # resolução: menor -> MAIOR
]
```

A modulação de menor para maior no capítulo final é o que produz a sensação de
"resolução épica". Acrescente um *swell* de 26 s no fecho.

Reverb barato e convincente: banco de *delays* com ganhos decrescentes + passa-baixa.

### 6.3 Processar áudio longo sem estourar a RAM

12 minutos a 44,1 kHz em float64 = 250 MB por array. Três regras:

1. Use `float32` em tudo.
2. Aplique reverb **em blocos de 60 s com 3 s de sobreposição**, não no array inteiro.
3. Escreva o WAV/AAC **em pedaços** via `proc.stdin.write()`, não de uma vez.

```python
BL, OV = int(60*SR), int(3*SR)
i = 0
while i < len(mix):
    a = max(0, i-OV); b = min(len(mix), i+BL)
    out[i:b] = reverb(mix[a:b].copy())[i-a:]
    i = b
```

### 6.4 Mixagem: deixe o ffmpeg fazer o trabalho pesado

Minha primeira versão fazia *ducking* em NumPy e foi **morta pelo OOM killer duas vezes**.
A versão que funciona usa `sidechaincompress` do ffmpeg:

```bash
# 1) Posiciona cada bloco de narração no tempo certo
for i in 0..9: "[$i:a]adelay=${ms}|${ms},volume=1.9[n$i]"
amix=inputs=10:normalize=0 -> nar_all.wav

# 2) Música abaixa automaticamente sob a voz
[1:a]atrim=0:708,volume=0.95[mus];
[0:a]asplit=2[nar1][key];
[mus][key]sidechaincompress=threshold=0.02:ratio=9:attack=25:release=420:makeup=1[musd];
[nar1][musd]amix=inputs=2:normalize=0:duration=first[m];
[m]alimiter=level_in=1:level_out=0.92:limit=0.96,afade=t=out:st=702:d=6[out]
```

Rápido, estável e com resultado melhor que o meu compressor manual.

---

## 7. Render e entrega

### 7.1 Loop de encoding

```python
cmd = [ff, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
       "-r", "24", "-i", "-", "-an",
       "-vf", "scale=1920:1080:flags=lanczos",
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "25",
       "-pix_fmt", "yuv420p", out]
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, ...)
for f in range(n):
    proc.stdin.write(to_bytes(fn(f/FPS, T)))
```

**CRF por objetivo:** 17–18 arquivo-mestre (grande demais para o sandbox);
**25 é o ponto ideal** para entrega (5–30 MB por capítulo, qualidade excelente);
27–28 se precisar apertar mais.

### 7.2 Entrega em capítulos — o padrão recomendado

Não tente entregar um MP4 único de 600 MB. Ele **não sobrevive ao snapshot**.

```python
# Cada capítulo recebe o trecho correspondente da mixagem completa
subprocess.run([FF, "-y", "-i", src,
    "-ss", f"{acc:.3f}", "-t", f"{T:.3f}", "-i", "mix_final.m4a",
    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", dst])
acc += T
```

Nomeie de forma descritiva e ordenável: `Tema_01_Abertura.mp4`, `Tema_02_....mp4`.
Como todos compartilham os mesmos parâmetros de codificação, o usuário pode concatená-los
depois sem recodificar.

**Protocolo de entrega (siga à risca):**

1. Renderize um lote de 3 a 4 capítulos.
2. Gere os MP4 com áudio, na **raiz** do workspace.
3. `present_file` em um deles, liste os demais em tabela.
4. **Peça para o usuário baixar e confirmar.**
5. Só então apague e renderize o próximo lote.

Ignorar o passo 4 foi o que causou a perda de arquivos três vezes no projeto original.

### 7.3 Legendas

Distribua cada bloco de narração por sentenças, proporcionalmente ao número de caracteres,
dentro da duração **real** do áudio:

```python
sents = re.split(r"(?<=[.!?:])\s+", bloco)
tot = sum(len(s) for s in sents)
for s in sents:
    sd = duracao_real * len(s) / tot        # proporcional ao comprimento
    emitir(cur, cur+sd-0.06, wrap(s, 46))   # 2 linhas, máx. 46 caracteres
    cur += sd
```

Não é sincronia perfeita por palavra, mas fica dentro de ~0,3 s e é indistinguível na
prática para narração corrida.

---

## 8. Controle de qualidade

### 8.1 Contact sheets — seu principal instrumento

**Nunca renderize um filme inteiro sem antes olhar frames.** Antes de cada render longo:

```python
tests = [(scene1, 66, [0.15, 0.55, 0.85]), (scene2, 76, [0.2, 0.5, 0.9]), ...]
for f, T, ps in tests:
    for p in ps:
        img = f(p*T, T)
        Image.fromarray((img*255).astype(np.uint8)).save(f"tests/{f.__name__}_{p}.jpg")
# depois monte uma folha de contato e LEIA a imagem
```

Monte em grade, abra com `read_file` e **inspecione de verdade**. Procure por:

- [ ] Texto cortado nas bordas ou sobreposto a outro texto
- [ ] Partículas esparsas demais (parece poeira, não fluido)
- [ ] Elementos pequenos demais no quadro
- [ ] Padrões de grade visíveis onde deveria haver aleatoriedade
- [ ] Formas erradas (espirais que não espiralam, discos que não têm sombra)
- [ ] Rótulos de duas cenas aparecendo ao mesmo tempo na transição

No projeto original, sete rodadas de contact sheet pegaram: espirais quebradas
(a fase da espiral logarítmica estava errada), cubo sem estrutura de fluxo (faltavam
*streamlines*), disco de acreção sem profundidade (faltava separar frente/trás),
grade visível na cena 5, texto cortado e rótulos sobrepostos. **Cada uma dessas seria um
re-render de 30 a 100 minutos se descoberta depois.**

### 8.2 Espiral logarítmica — acerte a fase

Erro que cometi e vale documentar. Esta versão produz um borrão radial:

```python
th = th0 + np.log(r/R)/b - om*t        # ERRADO: gira a espiral inteira
```

O correto é girar o **ângulo material** e derivar a banda a partir dele, para que a
espiral permaneça estacionária enquanto a matéria flui através dela:

```python
ph = th + om*t                                      # ângulo material (partícula gira)
f  = arms * (ph - np.log(r/R + 0.06)/b)             # fase da banda
band = (0.5 + 0.5*np.cos(f)) ** 2.2                 # bandas nítidas
```

Com `om = spin/(0.30 + (r/R)**1.45)` você ganha rotação diferencial — centro girando mais
rápido que a borda — que é o que torna o furacão convincente.

### 8.3 Verificação do arquivo final

```bash
ffmpeg -i final.mp4 2>&1 | grep -E "Duration|Stream"
for t in 30 160 300 500 690; do ffmpeg -ss $t -i final.mp4 -frames:v 1 out_$t.jpg; done
```

Extraia frames do MP4 **montado** (não das cenas isoladas) e olhe. Foi assim que descobri
o corte de texto na cartela final, que não aparecia nos testes de cena.

---

## 9. Orçamento de tempo (2 núcleos, 2 GB)

| Fase | Tempo | Observações |
|---|---|---|
| Planejamento e roteiro | 10–15 min | escrever os 10 blocos de narração |
| Narração TTS | 2 min | **em paralelo**, tudo numa resposta |
| Motor + cenas | 40–60 min | maior parte do trabalho de código |
| Iteração com contact sheets | 30–45 min | 5 a 8 rodadas; não pule |
| Trilha sonora | 5 min | síntese + reverb em blocos |
| Mixagem | 2 min | via ffmpeg |
| **Render** | **90–120 min** | 2 processos paralelos, 1440×808 |
| Montagem e entrega | 10 min | em lotes, com confirmação |

Render é o gargalo. Meça **antes** de começar:

```python
for f, T in PLAN:
    f(T*0.5, T)                              # aquece caches
    t0 = time.time()
    for i in range(3): f(T*0.5 + i*0.04, T)
    print(f.__name__, (time.time()-t0)/3, "s/frame")
```

Se o total passar de ~2 horas em um núcleo, otimize antes: reduza contagem de partículas,
baixe a resolução base, reduza passos de *streamline*, cacheie mais fundos.

---

## 10. Snippets de referência

### 10.1 Campo solenoidal (divergência zero) via curl-noise

Para qualquer fluido incompressível. `u = ∇ × A`, então `∇·u = 0` por construção:

```python
class CurlField:
    def vel(self, P, t, eps=0.09):
        # rot(A,B,C) = (dC/dy - dB/dz, dA/dz - dC/dx, dB/dx - dA/dy)
        return np.stack([dCdy - dBdz, dAdz - dCdx, dBdx - dAdy], -1)
```

Value-noise 3D vetorizado com interpolação suave `t*t*(3-2*t)` em cada eixo.

### 10.2 Linhas de corrente (muito mais bonito que pontos soltos)

Integre **para trás** a partir de cada partícula e faça *splat* em cada passo:

```python
Q = P.copy()
for k in range(18):
    sx, sy, zc = project(Q, ang, elev, rad)
    wgt = (1 - k/18) ** 1.1                    # rastro que desvanece
    splat(pc, sx, sy, 0.16*wgt*(4.6/zc)**1.8*(0.35+1.2*sn), col)
    Q = Q - field.vel(Q, t) * 0.032            # passo para trás
```

5 000 partículas × 18 passos ficam muito melhores que 90 000 pontos isolados.

### 10.3 Disco de acreção com oclusão correta

O truque é desenhar em três camadas, na ordem:

```python
near = np.sin(th) > 0                  # lado próximo, à frente do buraco
# 1) lado distante
splat(far, x[~near], y[~near], ...)
# 2) sombra do horizonte apagando o que está atrás
c *= (1 - smoothstep(Rin*1.00, Rin*0.88, d)[..., None] * 0.96)
# 2b) anel de fóton + arco de lente gravitacional (só na metade de cima)
arc = np.exp(-((d - Rin*1.30)/(Rin*0.14))**2) * np.clip(-(_YY-cy)/(Rin*1.1), 0, 1)
# 3) lado próximo POR CIMA de tudo
splat(nearc, x[near], y[near], ...)
```

Sem a separação frente/trás o disco parece um anel chapado.

### 10.4 Render em pedaços para cenas caras

```python
a, b = n*part//nparts, n*(part+1)//nparts
if idx == CENA_COM_ESTADO and a > 0:
    for f in range(a):                 # fast-forward só da física, sem render
        v = field.vel(P, f/FPS) * 1.35
        P += v / FPS
        P[np.abs(P) > 1.0] = ...
for f in range(a, b):
    proc.stdin.write(to_bytes(fn(f/FPS, T)))
```

Metades renderizadas em paralelo e concatenadas com `-c copy` — sem recodificar.

### 10.5 Funções de timing

```python
def smoothstep(a, b, x):
    t = np.clip((x-a)/max(b-a, 1e-9), 0, 1)
    return t*t*(3-2*t)

# entra e sai
alpha = smoothstep(0.30, 0.40, p) * (1 - smoothstep(0.62, 0.70, p))
# cartelas em cascata
for i, (txt, t0) in enumerate(bullets):
    a = smoothstep(t0, t0+0.05, p) * (1 - smoothstep(0.90, 0.96, p))
```

Use **sempre** `p = t/T` normalizado. Assim, mudar a duração de uma cena não quebra o
timing interno de nada.

---

## 11. Checklist de execução

**Recursos (seção 2)**
- [ ] `pip install imageio-ffmpeg` executado nesta sessão
- [ ] Bootstrap da seção 2.8 rodado; ffmpeg respondendo
- [ ] Fontes confirmadas com `fc-list` (não presuma nada além de DejaVu)
- [ ] Nenhum ativo de terceiros no produto final

**Planejamento**
- [ ] `ASSUNTO` e `ROTEIRO_INICIAL` claros; ambiguidades perguntadas
- [ ] 10 blocos de narração escritos (~1100 caracteres cada)
- [ ] Cada capítulo com um arquétipo visual concreto atribuído
- [ ] Duração realista comunicada ao usuário

**Áudio**
- [ ] Voz audicionada com trecho real do roteiro
- [ ] 10 blocos de TTS gerados em paralelo
- [ ] Durações medidas → `PLAN` definido
- [ ] Trilha sintetizada com curva de intensidade e resolução em maior
- [ ] Mixagem com sidechain via ffmpeg (não NumPy)

**Vídeo**
- [ ] `core.py` com splat, finish_parts, bloom, grade, text_layer, eq_image
- [ ] Resolução base múltipla de 8; escala para 1080p no encoder
- [ ] Caches de fundo, estrelas e equações
- [ ] Contact sheet revisado — **de verdade** — a cada mudança visual
- [ ] Tempo de render medido antes de disparar
- [ ] `.ok` por capítulo, 2 processos paralelos com índices intercalados

**Entrega**
- [ ] Capítulos de 5 a 30 MB, com áudio embutido, na raiz
- [ ] Nomes descritivos e ordenáveis
- [ ] `.srt` gerado a partir das durações reais
- [ ] Entrega em lotes, **com confirmação de download antes de apagar**
- [ ] Workspace abaixo de ~90 MB ao fim de cada turno
- [ ] `narracao.txt` e código-fonte preservados

---

## 12. Erros a não repetir

| Erro | Consequência | Correção |
|---|---|---|
| MP4 único de 629 MB | perdido no snapshot, duas vezes | entregar em capítulos de 5–30 MB |
| Apagar antes de confirmar download | re-render de 25 min | pedir confirmação explícita |
| Ducking de áudio em NumPy | OOM killer, 2× | `sidechaincompress` do ffmpeg |
| `H = 810` | `cannot reshape array` | dimensões múltiplas de 8 |
| `MathTextParser("bitmap")` | `ValueError` | `fig.text` + `savefig` |
| Escalar fontes por `W/1920` | cartela continuou cortada | quebrar a linha, manter corpo absoluto |
| Fase errada na espiral log | borrão radial sem braços | girar `ph`, derivar `f` a partir dele |
| `np.bincount` no lugar de `np.add.at` | 2× mais lento | manter `np.add.at` |
| Não separar frente/trás no disco | anel chapado sem profundidade | três camadas com sombra no meio |
| Grade regular de partículas | padrão de moiré visível | posições aleatórias, não `meshgrid` |
| Render nativo em 1080p | 230 min de CPU | 1440×808 + Lanczos = 98 min |
| Esquecer `pip install imageio-ffmpeg` | `ModuleNotFoundError` a cada turno | reinstalar no início de cada mensagem |

---

## 13. Prompt sugerido para acionar este playbook

```
Crie um documentário científico em vídeo sobre <ASSUNTO>, seguindo integralmente o
PLAYBOOK_VIDEO_DOCUMENTARIO.md deste repositório.

Roteiro inicial:
<ROTEIRO_INICIAL — 10 capítulos com VISUAL / TEXTO / EQUAÇÕES / NARRAÇÃO>

Especificações: 16:9, 1080p, 24 fps, <ESTILO>, narração em <IDIOMA>,
trilha eletrônica ambiente com tensão crescente e resolução no final.
Premissa a reforçar na abertura, no meio e na conclusão: <PREMISSA>.

Entregue em capítulos separados, um lote por vez, pedindo confirmação de download
antes de gerar o lote seguinte.
```
