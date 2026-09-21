# Agente de Prompt para Geração de Imagens

## O que é este documento

Este é um agente de prompt inteligente que vai te ajudar a transformar sua ideia em uma imagem perfeita. Ele funciona em três etapas:

1. **Entrevista** —.make perguntas para entender exatamente o que você quer
2. **Otimização** — transforma suas respostas no melhor prompt possível
3. **Configuração** — recomenda o modelo ideal e configurações do ComfyUI

---

## Etapa 1: Entrevista — Respondas estas perguntas

### 1.1 Visão Geral

| Pergunta | Sua Resposta |
|----------|---------------|
| O que você quer ver na imagem? (Descrição básica) | |
| Qual é o objetivo? (Arte, concept art, foto realista, animação, etc.) | |
| Para que用途? (Rede social, jogo, portfolio, peça de arte, etc.) | |

### 1.2 Assunto Principal

| Pergunta | Sua Resposta |
|----------|---------------|
| Quem ou o que aparece na imagem? (Pessoa, criatura, objeto, paisagem) | |
| Quais são as características principais do sujeito? (Idade, gênero, estilo, cor, expressão) | |
| O que ele está fazendo? (Pose, ação, atividade) | |
| Há algum detalhe específico que você quer destacar? | |

### 1.3 Ambiente e Contexto

| Pergunta | Sua Resposta |
|----------|---------------|
| Onde a cena acontece? (Interior, exterior, espaço imaginário) | |
| Qual é a iluminação? (Luz natural, artificial, neon, dramtica, etc.) | |
| Qual horário do dia? (Manhã, pôr do sol, noite, amanhecer) | |
| Há algum ambiente ou atmosfera específica? (Sombrio, alegre, mystico, futurista) | |

### 1.4 Estilo Artístico

| Pergunta | Sua Resposta |
|----------|---------------|
| Qual estilo visual você prefere? | |
| Referências de artistas ou obras que você gosta? | |
| Nível de detalhe desejado? (Minimalista, detalhado, hiper-realista) | |
| Paleta de cores preferida? (Quente, fria, vibrante, apagada, específica) | |

### 1.5 Aspectos Técnicos

| Pergunta | Sua Resposta |
|----------|---------------|
| Proporção da imagem? (1:1, 16:9, 4:3, 9:16) | |
| Resolução necessária? | |
| Precisa de texto na imagem? | |
| Há elementos que devem ser evitados? | |

### 1.6 ComfyUI Específico (se aplicável)

| Pergunta | Sua Resposta |
|----------|---------------|
| Você está usando ComfyUI? | |
| Já tem um workflow base? | |
| Há modelos específicos que você quer usar? | |

---

## Etapa 2: Composição do Prompt Otimizado

### Estrutura do Prompt Final

```
[Sujeito principal] + [Ação/Pose] + [Ambiente] + [Iluminação] + [Estilo] + [Detalhes técnicos]
```

### Exemplos de Prompts Otimizados

#### Exemplo 1: Personagem Fantasia
```
"Portrait of an elderly wizard with long silver beard, wearing intricate purple robes embroidered with golden runes, holding a glowing oak staff, standing in ancient library filled with floating books, dramatic candlelight illumination, moody atmospheric fog, fantasy art style reminiscent of Brom and Greg Rutkowski, highly detailed, 8k, digital painting"
```

#### Exemplo 2: Paisagem Futurista
```
"Futuristic neon-lit cityscape at night, massive holographic advertisements, flying vehicles with light trails, rain-soaked streets reflecting neon lights, Asian cyberpunk architecture, moody atmosphere, cinematic lighting, blade runner 2049 aesthetic, concept art, highly detailed, 8k render"
```

#### Exemplo 3: Retrato Realista
```
"Professional headshot of a young woman with auburn hair, warm brown eyes, natural makeup, soft smile, wearing a fitted black blazer, studio lighting with subtle rim light, neutral gray background, shallow depth of field, photorealistic, Canon 85mm f/1.4"
```

### Dicas de Prompt Engineering

| Técnica | Como Aplicar | Exemplo |
|---------|--------------|---------|
| **Peso de palavras** | Use parênteses para enfatizar | `(masterpiece:1.3), (best quality)` |
| **Negativos** | Liste o que NÃO quer | `low quality, blurry, distorted` |
| **Pós-processamento** | Inclua comandos de finish | `unreal engine 5 render, octane render` |
| **Composição** | Especifique ângulo | `wide angle, close-up, from below` |
| **Estilo de câmera** | Defina tipo de lente | `35mm film, f/1.8, bokeh` |

---

## Etapa 3: Recomendação de Modelos

### Por Categoria

| Categoria | Melhor Modelo | Quando Usar |
|-----------|---------------|-------------|
| **Realismo** | SDXL Realistic, Juggernaut XL, DreamShaper | Retratos, fotos, cenas realistas |
| **Arte Digital** | Midjourney, Stable Diffusion 1.5/2.1 | Ilustrações, concept art |
| **Anime/Anime-style** | Anything V5, A to Zovya, MeinaMix | Estilo japonês, anime |
| **Fantasia/Ficção** | FantasyGen, DreamShaper, RevAnimated | Personagens fantásticos, cenas épicas |
| **Arquitetura** | Architectural Diffusion | Interiores, exteriores, design |
| **Moda/Produto** | ProductEcom, CL Stable | Moda, produtos, e-commerce |

### Comparativo de Modelos Populares

| Modelo | Pontos Fortes | Pontos Fracos | Melhor Para |
|--------|---------------|---------------|-------------|
| **Midjourney v6** | Qualidade artística, coerência | Custo, menos controle | Arte conceitual |
| **DALL-E 3** | Compreensão de texto, fidelidade | Menor qualidade em detalhes | Ideias abstratas |
| **Stable Diffusion XL** | Gratuito, controlável | Requer hardware | Uso pessoal |
| **Leonardo.ai** | Previews, múltiplos modelos | Interface complexa | Experimentação |
| **ComfyUI (local)** | Máximo controle, gratuito | Curva de aprendizado | Produção profissional |

---

## Etapa 4: Configurações ComfyUI

### Workflow Recomendado por Tipo

#### 4.1 Retrato Realista

```
┌─────────────────┐
│ Load Checkpoint │ ← "juggernautXL_v8.safetensors"
└────────┬────────┘
         ↓
┌─────────────────┐
│ CLIP Text Encode│ ← Positive: "portrait of [descrição], photorealistic, 8k"
└────────┬────────┘
         ↓
┌─────────────────┐
│ CLIP Text Encode│ ← Negative: "low quality, blurry, deformed"
└────────┬────────┘
         ↓
┌─────────────────┐
│ KSampler        │ ← Steps: 25-35, CFG: 6-8, Scheduler: normal
└────────┬────────┘
         ↓
┌─────────────────┐
│ VAE Decode      │
└────────┬────────┘
         ↓
┌─────────────────┐
│ Save Image      │
└─────────────────┘
```

#### 4.2 Arte Estilizada (Anime/Fantasia)

```
┌─────────────────┐
│ Load Checkpoint │ ← "anything_v5.safetensors" ou "meinamix"
└────────┬────────┘
         ↓
┌─────────────────┐
│ Lora Stack      │ ← Adicionar LoRAs de estilo
└────────┬────────┘
         ↓
│ ... (mesmo fluxo) │
```

### Parâmetros Recomendados

| Parâmetro | Valor Realista | Valor Artístico | Valor Anime |
|-----------|----------------|-----------------|-------------|
| **Steps** | 25-35 | 20-30 | 20-25 |
| **CFG Scale** | 6-8 | 7-10 | 7-12 |
| **Sampler** | DPM++ 2M Karras | Euler a | Euler |
| **Scheduler** | Normal | Exponential | Simple |
| **Denoise** | 1.0 | 0.7-0.9 | 0.8 |

### Configurações Avançadas

#### ControlNet (para poses e composição)

| Modelo ControlNet | Uso | Weight |
|-------------------|-----|--------|
| Canny | Estrutura, contornos | 0.5-0.8 |
| Depth | Profundidade, perspectiva | 0.6-0.9 |
| Pose | Pose de pessoa | 0.8-1.0 |
| Scribble | Desenho básico | 0.7-1.0 |
| Segments | Segmentação semântica | 0.5-0.7 |

#### Upscaling (para 4K+)

```
┌─────────────────┐
│ Ultimate SD Upscale│
└────────┬────────┘
         ├── Tile size: 512
         ├── Overlap: 64
         └── Scale factor: 2
```

### LoRAs Recomendados por Estilo

| Estilo | LoRA | Weight Sugerida |
|--------|------|-----------------|
| Realismo | detail_enhancer | 0.3-0.5 |
| Cinema | cinematics | 0.4-0.7 |
| Anime | anime_style | 0.6-0.8 |
| Fantasy | fantasy_style | 0.5-0.7 |
| Cyberpunk | cyberpunk_style | 0.5-0.8 |
| Retrato | portrait_plus | 0.3-0.5 |

---

## Checklist Pré-Geração

Antes de gerar sua imagem, verifique:

- [ ] A descrição do sujeito está clara e específica?
- [ ] O ambiente e iluminação estão definidos?
- [ ] O estilo artístico está indicado?
- [ ] Você incluiu prompt negativo?
- [ ] A proporção está correta para seu uso?
- [ ] O modelo escolhido é adequado para o tipo de imagem?
- [ ] As configurações do sampler/steps estão otimizadas?

---

## Modelo de Prompt Final

Copie e preencha este modelo:

```
Prompt Positivo:
[Sujeito] + [Ação] + [Ambiente] + [Iluminação] + [Estilo] + [Qualidade]

Prompt Negativo:
(low quality, worst quality, blurry, deformed, disfigured, bad anatomy)

Modelo Sugerido: ________________
Sampler: ________________
Steps: ________________
CFG: ________________
Resolução: ________________
LoRAs (opcional): ________________
```

---

## Exemplos Práticos

### Caso 1: "Quero uma capa de livro de fantasia"

**Entrevista respondida:**
- Personagem: guerreira élfica com armadura
- Ação: segurando espada mágica
- Ambiente: floresta encantada ao pôr do sol
- Estilo: arte épica fantasy

**Prompt gerado:**
```
"Epic fantasy warrior elf female, flowing silver hair, ornate elven armor with leaf motifs, holding radiant sword emitting golden light, standing in enchanted forest at golden hour, volumetric sunlight filtering through ancient trees, magical particles floating, epic fantasy art style by Greg Rutkowski and Alphonse Mucha, dramatic lighting, masterpiece, best quality, highly detailed, 8k digital painting, book cover style"
```

**Configuração ComfyUI:**
- Checkpoint: `juggernautXL_v8.safetensors` ou `revAnimated_v122`
- Steps: 30
- CFG: 7.5
- Sampler: DPM++ 2M Karras
- Adicionar LoRA: `fantasy_style_v1` (weight 0.6)

---

### Caso 2: "Preciso de um logo minimalista"

**Entrevista respondida:**
- Sujeta: letra "A" estilizada
- Estilo: geométrico, moderno
- Uso: marca pessoal

**Prompt gerado:**
```
"Minimalist geometric letter A logo design, clean lines, modern abstract style, black and white, vector style, simple yet elegant, professional, negative space design, corporate identity, trending on behance, minimalist logo"
```

**Configuração ComfyUI:**
- Checkpoint: `logosdxl.safetensors`
- Steps: 20
- CFG: 5-6 (logos precisam de menos CFG)
- Adicionar: `logo_design_lora`
- Resolución: 1024x1024

---

### Caso 3: "Uma foto profissional corporativa"

**Entrevista respondida:**
- Pessoas: executivo, homem, 40 anos
- Estilo: headshot corporativo
- Uso: LinkedIn, site

**Prompt gerado:**
```
"Professional corporate headshot of a confident middle-aged businessman, short dark hair, wearing tailored navy suit, white crisp shirt, red tie, natural smile, looking at camera, professional studio lighting with soft boxes, neutral light gray background, shallow depth of field, bokeh, Canon EOS 5D Mark IV, 85mm f/1.4 lens, photorealistic, high detail, 8k"
```

**Configuração ComfyUI:**
- Checkpoint: `juggernautXL_v8.safetensors`
- Steps: 30
- CFG: 6
- Sampler: DPM++ 2M
- Adicionar: `portrait_plus` LoRA (weight 0.4)

---

## Recursos Adicionais

### Links Úteis

- [Hugging Face](https://huggingface.co/) — Modelos gratuitos
- [Civitai](https://civitai.com/) — LoRAs e modelos
- [ComfyUI Workflows](https://comfyworkflows.com/) — Workflows prontos
- [Prompt Hero](https://prompthero.com/) — Referências de prompts

### Comandos Úteis para Midjourney

| Comando | Função |
|---------|--------|
| `--ar 16:9` | Proporção |
| `--v 6` | Versão |
| `--s 750` | Stylize (0-1000) |
| `--iw 0.7` | Image weight |
| `--no [element]` | Negar elemento |
| `--seed [n]` | Repetir geração |

---

*Documento criado pelo Agente de Prompt — Use este guia para transformar suas ideias em imagens perfeitas.*