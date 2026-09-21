/* VideoVortex — Gerador de roteiro de vendas (PT-BR, 100% local).
 * Gera: roteiro completo com minutagem, gancho de 15s, legenda p/ redes,
 * pitch de WhatsApp e cenas por foto (usadas nas legendas do vídeo). */

(function (global) {
  "use strict";

  const TONES = {
    persuasivo: {
      label: "Persuasivo",
      openers: [
        "Seja bem-vindo ao imóvel que vai mudar o seu conceito de morar bem.",
        "Prepare-se: o que você vai ver agora é raro no mercado.",
        "Imagine acordar todos os dias exatamente onde você sempre sonhou.",
      ],
      adjectives: ["incrível", "surpreendente", "imperdível", "espetacular"],
      ctas: [
        "Agende agora a sua visita — imóveis assim não ficam disponíveis por muito tempo.",
        "Chame no WhatsApp e garanta a sua visita ainda hoje.",
        "Não deixe para depois: clique, chame e venha conhecer pessoalmente.",
      ],
    },
    luxo: {
      label: "Alto padrão / Luxo",
      openers: [
        "Alguns endereços não se compram — se conquistam. Seja bem-vindo a um deles.",
        "Exclusividade, design e sofisticação em cada metro quadrado.",
        "Uma curadoria de alto padrão para quem reconhece o extraordinário.",
      ],
      adjectives: ["exclusivo", "sofisticado", "impecável", "extraordinário"],
      ctas: [
        "Visitas privadas mediante agendamento. Fale com nosso especialista.",
        "Este nível de exclusividade merece uma visita exclusiva. Agende a sua.",
        "Entre em contato para uma apresentação personalizada.",
      ],
    },
    familiar: {
      label: "Familiar / Acolhedor",
      openers: [
        "Lar não é um lugar — é uma sensação. E ela mora aqui.",
        "Aquele cantinho onde a família se reúne e a vida acontece.",
        "Se você procura um lar de verdade, acabou de encontrar.",
      ],
      adjectives: ["aconchegante", "acolhedor", "tranquilo", "cheio de vida"],
      ctas: [
        "Venha sentir de perto: agende uma visita com a família.",
        "Traga quem você ama para conhecer. Agende sua visita.",
        "O próximo capítulo da sua família começa com uma visita.",
      ],
    },
    investidor: {
      label: "Investidor",
      openers: [
        "Números primeiro, emoção depois: este ativo se paga sozinho.",
        "Rentabilidade, liquidez e valorização em um único endereço.",
        "O mercado procura; poucos encontram. Analise esta oportunidade.",
      ],
      adjectives: ["estratégico", "rentável", "sólido", "valorizado"],
      ctas: [
        "Solicite a análise completa de rentabilidade e agende uma visita técnica.",
        "Ativos assim saem rápido da carteira. Fale com o especialista hoje.",
        "Peça a projeção de ROI e venha conhecer o ativo pessoalmente.",
      ],
    },
    jovem: {
      label: "Jovem / Descolado",
      openers: [
        "Seu próximo apê é aqui — e o rolê começa no tour.",
        "Spoiler: você vai querer se mudar ainda hoje.",
        "Match perfeito entre estilo, praticidade e localização.",
      ],
      adjectives: ["estiloso", "prático", "conectado", "cheio de vibe"],
      ctas: [
        "Manda um 'quero visitar' no WhatsApp e bora conhecer.",
        "Curtiu? Agenda a visita e vem sentir a vibe ao vivo.",
        "Não fica só no vídeo — vem ver pessoalmente. Chama no direct.",
      ],
    },
  };

  const ROOM_LINES = {
    sala: [
      "a sala ampla e iluminada, o coração social do imóvel",
      "a sala de estar com ótimo aproveitamento e luz natural",
      "o living generoso, perfeito para receber e relaxar",
    ],
    quarto: [
      "o quarto com excelente ventilação e espaço de sobra",
      "o dormitório aconchegante, pensado para o seu descanso",
      "a suíte privativa com conforto de hotel",
    ],
    cozinha: [
      "a cozinha funcional, pronta para o dia a dia e para receber",
      "a cozinha planejável com ótima bancada e iluminação",
      "o espaço gourmet integrado, feito para bons momentos",
    ],
    banheiro: [
      "o banheiro com acabamento caprichado e boa ventilação",
      "o banheiro moderno, prático e bem resolvido",
    ],
    varanda: [
      "a varanda com vista e aquele respiro que todo lar precisa",
      "o terraço/varanda, extensão natural da sala para o ar livre",
    ],
    escritorio: [
      "o home office silencioso, ideal para o trabalho remoto",
      "o espaço de estudos/trabalho com ótima luz para o dia todo",
    ],
    area: [
      "a área externa com potencial total para lazer e convivência",
      "o quintal/área livre, um luxo cada vez mais raro",
    ],
    garagem: ["a vaga de garagem demarcada e de fácil acesso"],
    fachada: [
      "a fachada bem conservada, o cartão de visitas do imóvel",
      "a entrada do condomínio/rua, segura e bem cuidada",
    ],
    default: [
      "este ambiente versátil, cheio de possibilidades",
      "mais um espaço bem resolvido do imóvel",
      "este canto especial, repare nos detalhes",
    ],
  };

  const STAGING_LINES = [
    "Repare na simulação: mesmo vazio hoje, veja como o ambiente ganha vida mobiliado.",
    "O imóvel está vazio — e isso é uma vantagem: veja a sugestão de mobiliário na tela.",
    "Visualize o potencial: esta é uma simulação do ambiente mobiliado.",
  ];

  function detectRoom(label) {
    const l = (label || "").toLowerCase();
    if (/sala|living|estar/.test(l)) return "sala";
    if (/quarto|suite|su.te|dormit/.test(l)) return "quarto";
    if (/cozinha|gourmet|churras/.test(l)) return "cozinha";
    if (/banheiro|wc|lavabo/.test(l)) return "banheiro";
    if (/varanda|terra.o|sacada/.test(l)) return "varanda";
    if (/escrit|office|estudo/.test(l)) return "escritorio";
    if (/quintal|jardim|piscina|externa|area/.test(l)) return "area";
    if (/garagem|vaga/.test(l)) return "garagem";
    if (/fachada|entrada|condom|predio|pr.dio/.test(l)) return "fachada";
    return "default";
  }

  function pick(arr, seed) {
    if (!arr || !arr.length) return "";
    return arr[Math.abs(seed) % arr.length];
  }

  function fmtTime(sec) {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }

  function money(v) {
    return (v || "").toString().trim();
  }

  function infoLine(info) {
    const parts = [];
    if (info.area) parts.push(`${info.area} m²`);
    if (info.quartos) parts.push(`${info.quartos} quarto(s)`);
    if (info.banheiros) parts.push(`${info.banheiros} banheiro(s)`);
    if (info.vagas) parts.push(`${info.vagas} vaga(s)`);
    return parts.join(" · ");
  }

  function generateScript(info, photos, toneKey, targetSeconds, variant) {
    const tone = TONES[toneKey] || TONES.persuasivo;
    const v = variant || 0;
    const title = info.titulo?.trim() || "Imóvel em destaque";
    const addr = info.endereco?.trim() || "localização privilegiada";
    const specs = infoLine(info);
    const price = money(info.preco);
    const diffs = (info.diferenciais || "")
      .split(/[\n,;]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 5);
    const adj = pick(tone.adjectives, v + 1);
    const opener = pick(tone.openers, v);
    const cta = pick(tone.ctas, v + 2);

    // Distribuição do tempo: gancho 5s, apresentação, tour, diferenciais, CTA.
    const total = Math.max(20, targetSeconds || 60);
    const tHook = Math.min(8, Math.round(total * 0.12));
    const tIntro = Math.round(total * 0.18);
    const tCta = Math.round(total * 0.14);
    const tDiff = diffs.length ? Math.round(total * 0.12) : 0;
    const tTour = Math.max(10, total - tHook - tIntro - tCta - tDiff);

    const lines = [];
    const scenes = [];
    let t = 0;

    // GANCHO
    lines.push({ at: t, tag: "GANCHO", text: `${opener}` });
    if (price) lines[0].text += ` E o melhor: ${price}.`;
    t += tHook;

    // APRESENTAÇÃO
    let intro = `Este é o ${title}, em ${addr}.`;
    if (specs) intro += ` São ${specs}, em uma planta ${adj}.`;
    if (info.tipo) intro += ` Um ${info.tipo.toLowerCase()} que une conforto, praticidade e ótima localização.`;
    lines.push({ at: t, tag: "APRESENTAÇÃO", text: intro });
    t += tIntro;

    // TOUR cômodo a cômodo
    const n = Math.max(1, photos.length);
    const perPhoto = tTour / n;
    photos.forEach((p, i) => {
      const room = detectRoom(p.label);
      const desc = pick(ROOM_LINES[room], v + i);
      let text =
        i === 0
          ? `Começamos o tour por ${desc}.`
          : i === n - 1
            ? `E finalizamos em ${desc}.`
            : `Agora, ${desc}.`;
      if (p.empty) text += " " + pick(STAGING_LINES, v + i);
      const at = Math.round(t + perPhoto * i);
      lines.push({ at, tag: `TOUR — ${(p.label || "Ambiente").toUpperCase()}`, text });
      scenes.push({ photoId: p.id, label: p.label || `Ambiente ${i + 1}`, start: at, end: Math.round(t + perPhoto * (i + 1)), text });
    });
    t += tTour;

    // DIFERENCIAIS
    if (diffs.length) {
      lines.push({ at: t, tag: "DIFERENCIAIS", text: `E tem mais: ${diffs.join("; ")}.` });
      t += tDiff;
    }

    // CTA
    let closer = cta;
    if (info.corretor) closer += ` Fale com ${info.corretor}`;
    if (info.contato) closer += ` no ${info.contato}`;
    closer += ".";
    lines.push({ at: t, tag: "CHAMADA FINAL", text: closer });

    const full = [
      `ROTEIRO — ${title.toUpperCase()}`,
      `Tom: ${tone.label} · Duração alvo: ~${total}s · ${photos.length} ambiente(s)`,
      "",
      ...lines.map((l) => `[${fmtTime(l.at)}] ${l.tag}\n${l.text}`),
    ].join("\n\n");

    const hook =
      `${pick(tone.openers, v + 1)} ${title}, em ${addr}` +
      (specs ? `, com ${specs}` : "") +
      (price ? ` por ${price}` : "") +
      ". Veja o tour completo!";

    const caption = [
      `🏠 ${title}`,
      `📍 ${addr}`,
      specs ? `✨ ${specs}` : null,
      price ? `💰 ${price}` : null,
      diffs.length ? `⭐ ${diffs.slice(0, 3).join(" · ")}` : null,
      "",
      "🎥 Assista ao tour 360° completo no vídeo!",
      info.corretor || info.contato
        ? `📲 ${[info.corretor, info.contato].filter(Boolean).join(" — ")}`
        : null,
      "",
      "#imoveis #avenda #tourvirtual #corretor #lar #oportunidade",
    ]
      .filter((x) => x !== null)
      .join("\n");

    const whatsapp =
      `Olá! Vi o anúncio do *${title}* (${addr}` +
      (price ? ` — ${price}` : "") +
      `) e gostaria de agendar uma visita. ` +
      (info.corretor ? `Pode me ajudar, ${info.corretor.split(" ")[0]}?` : "Pode me ajudar?") +
      ` Obrigado!`;

    const words = full.split(/\s+/).length;
    return {
      full,
      hook,
      caption,
      whatsapp,
      scenes,
      // As linhas faladas, em ordem e com o tempo de cada uma. `full` é o roteiro
      // FORMATADO (com marcas de seção, feito para ler na tela); `lines` é o que a
      // narração fala — é daqui que saem os trechos de áudio e as legendas.
      lines,
      tone: tone.label,
      targetSeconds: total,
      wordCount: words,
      readSeconds: Math.round((words / 150) * 60),
    };
  }


  /* ==========================================================================
   * Verbalizer para TTS
   * --------------------------------------------------------------------------
   * O roteiro é escrito para ser LIDO (na tela) e depois FALADO. São duas coisas
   * diferentes: na tela "78 m² · R$ 650.000" é o que o corretor quer ver; no
   * ouvido, a voz neural lê "meme ao quadrado" se ninguém traduzir antes.
   *
   * verbalize() faz essa tradução: R$ → reais, m² → metros quadrados, (s) do
   * plural resolvido pela contagem, % → "por cento" e abreviações expandidas
   * (apto, qto, WC). A ordem das passagens importa (moeda ANTES de qualquer coisa
   * que mexa em número) e está documentada em cada trecho.
   *
   * O que NÃO se converte também é decisão: algarismo solto fica algarismo, porque
   * em português o numeral concorda em gênero com o substantivo ("1 vaga" é "uma
   * vaga", "200 vagas" é "duzentas") e a voz neural resolve isso melhor do que
   * uma tabela nossa. Ver o passo 6 de verbalize().
   * ======================================================================== */

  const NUM_UNI = [
    "zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove",
    "dez", "onze", "doze", "treze", "quatorze", "quinze", "dezesseis", "dezessete",
    "dezoito", "dezenove",
  ];
  const NUM_DEZ = ["", "", "vinte", "trinta", "quarenta", "cinquenta", "sessenta", "setenta", "oitenta", "noventa"];
  const NUM_CEM = ["", "cento", "duzentos", "trezentos", "quatrocentos", "quinhentos", "seiscentos", "setecentos", "oitocentos", "novecentos"];
  const NUM_GRUPO = ["", "mil", "milhão", "bilhão", "trilhão"];
  const NUM_GRUPO_PLURAL = ["", "mil", "milhões", "bilhões", "trilhões"];

  /** 1..999 por extenso ("cem" para 100, "cento e vinte" para 120). */
  function centenasPorExtenso(n) {
    if (n === 100) return "cem";
    const c = Math.floor(n / 100);
    const r = n % 100;
    let saida = c ? NUM_CEM[c] : "";
    if (r) {
      const resto = r < 20 ? NUM_UNI[r] : NUM_DEZ[Math.floor(r / 10)] + (r % 10 ? " e " + NUM_UNI[r % 10] : "");
      saida = saida ? saida + " e " + resto : resto;
    }
    return saida;
  }

  /**
   * Inteiro por extenso em PT-BR.
   *
   * A única decisão que realmente importa é onde entra o "e" entre os grupos:
   *
   *   1.500      → "mil e quinhentos"                       (com "e")
   *   1.234      → "mil duzentos e trinta e quatro"         (sem "e")
   *   1.100.000  → "um milhão e cem mil"                    (com "e")
   *   1.234.567  → "um milhão duzentos e trinta e quatro mil quinhentos e sessenta e sete"
   *
   * A regra que reproduz o uso: o "e" entra quando o ÚLTIMO grupo é menor que
   * 100 ou é centena cheia — ou seja, quando ele não tem "e" interno próprio.
   */
  function inteiroPorExtenso(n) {
    if (!isFinite(n)) return "";
    n = Math.trunc(n);
    if (n === 0) return "zero";
    if (n < 0) return "menos " + inteiroPorExtenso(-n);

    const grupos = [];
    let resto = n;
    while (resto > 0) {
      grupos.push(resto % 1000);
      resto = Math.floor(resto / 1000);
    }

    const partes = [];
    for (let i = grupos.length - 1; i >= 0; i--) {
      const v = grupos[i];
      if (!v) continue;
      if (i === 0) {
        partes.push(centenasPorExtenso(v));
      } else if (i === 1) {
        partes.push(v === 1 ? "mil" : centenasPorExtenso(v) + " mil");
      } else {
        const nome = v === 1 ? NUM_GRUPO[i] : NUM_GRUPO_PLURAL[i];
        partes.push((v === 1 ? "um " : centenasPorExtenso(v) + " ") + nome);
      }
    }
    if (partes.length === 1) return partes[0];

    const ultimoValor = grupos.find((v) => v > 0) || 0;
    const usaE = ultimoValor < 100 || ultimoValor % 100 === 0;
    return partes.slice(0, -1).join(" ") + (usaE ? " e " : " ") + partes[partes.length - 1];
  }

  /** "650.000" / "1.234,56" / "650000" → número (formato brasileiro). */
  function numeroBR(bruto) {
    if (bruto == null) return NaN;
    let t = String(bruto).trim();
    if (t.indexOf(",") >= 0) t = t.replace(/\./g, "").replace(",", ".");
    else if (/\.\d{3}(\D|$)/.test(t)) t = t.replace(/\./g, "");  // 1.234 é milhar, não decimal
    return parseFloat(t);
  }

  /** Valor em reais por extenso ("R$ 1.234,50" → "mil duzentos e trinta e quatro reais e cinquenta centavos"). */
  function reaisPorExtenso(bruto) {
    const num = numeroBR(bruto);
    if (!isFinite(num)) return "R$ " + bruto;
    const inteiro = Math.floor(Math.abs(num));
    const centavos = Math.round((Math.abs(num) - inteiro) * 100);

    const partes = [];
    if (inteiro > 0) {
      partes.push(inteiroPorExtenso(inteiro) + (inteiro === 1 ? " real" : " reais"));
    }
    if (centavos > 0) {
      partes.push(inteiroPorExtenso(centavos) + (centavos === 1 ? " centavo" : " centavos"));
    }
    if (!partes.length) return "zero reais";
    return partes.join(" e ");
  }

  /** Plural português para o marcador "(s)" — só o suficiente para o roteiro. */
  function pluralizar(palavra) {
    if (/[rz]$/i.test(palavra)) return palavra + "es";
    if (/s$/i.test(palavra)) return palavra;
    if (/l$/i.test(palavra)) return palavra.replace(/l$/i, "is");
    if (/m$/i.test(palavra)) return palavra.replace(/m$/i, "ns");
    if (/ão$/i.test(palavra)) return palavra.replace(/ão$/i, "ões");
    return palavra + "s";
  }

  // Unidades na ordem em que precisam ser aplicadas: as compostas (km²) antes das
  // simples (km), senão "km²" viraria "quilômetros²". A alternância é
  // não-capturante de propósito — com um grupo a mais o número chegaria
  // deslocado no callback e sairia da frase (bug que já aconteceu aqui: "78 m²"
  // virava só "metros quadrados").
  const UNIDADES = [
    [/(\d+(?:[.,]\d+)?)\s*(?:km²|km2)/gi, "quilômetro quadrado", "quilômetros quadrados"],
    [/(\d+(?:[.,]\d+)?)\s*(?:m²|m2)/gi, "metro quadrado", "metros quadrados"],
    [/(\d+(?:[.,]\d+)?)\s*(?:m³|m3)/gi, "metro cúbico", "metros cúbicos"],
    [/(\d+(?:[.,]\d+)?)\s*km\b/gi, "quilômetro", "quilômetros"],
    [/(\d+(?:[.,]\d+)?)\s*kg\b/gi, "quilo", "quilos"],
    [/(\d+(?:[.,]\d+)?)\s*cm\b/gi, "centímetro", "centímetros"],
    [/(\d+(?:[.,]\d+)?)\s*mm\b/gi, "milímetro", "milímetros"],
    [/(\d+(?:[.,]\d+)?)\s*m\b/gi, "metro", "metros"],
  ];

  const ABREV = [
    [/\baptos\b/gi, "apartamentos"], [/\bapto\b/gi, "apartamento"],
    [/\bqtos\b/gi, "quartos"], [/\bqto\b/gi, "quarto"],
    [/\bWC\b/g, "banheiro"], [/\bwc\b/g, "banheiro"],
    [/\bnº\s*/gi, "número "], [/\bn°\s*/gi, "número "],
    // atenção: depois de "." não existe \b (ponto e espaço são ambos não-palavra),
    // então a regex consome o espaço final em vez de exigir fronteira
    [/\bsr\.\s*/gi, "senhor "], [/\bsra\.\s*/gi, "senhora "],
    [/\bvc\b/gi, "você"], [/\bobs\.\s*/gi, "observação "],
  ];

  /** Tira o que não é fala (marcação, emoji, bullet) mas preserva o que tem som. */
  function limparParaFala(texto) {
    return String(texto || "")
      .replace(/\u00a0/g, " ")
      .replace(/[^\w\s.,;:!?%°º²³$()+\-/ªºáàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]/g, " ")
      .replace(/\s+/g, " ");
  }

  /**
   * Converte o texto do roteiro para o que deve ser FALADO.
   * @param {string} texto
   * @returns {string}
   */
  function verbalize(texto) {
    let t = limparParaFala(texto);

    // 1. moeda ANTES de mexer com números (senão "R$" fica órfão)
    t = t.replace(/R\$\s*([\d.,]+)/gi, (_, v) => " " + reaisPorExtenso(v) + " ");
    t = t.replace(/R\$(?!\s*[\d.,])/gi, " reais ");

    // 2. unidades (compostas primeiro, ver UNIDADES). O NÚMERO FICA: quem lê o
    //    algarismo é a voz ("78" → "setenta e oito"); aqui só trocamos o símbolo
    //    que ela não sabe pronunciar.
    UNIDADES.forEach(([re, singular, plural]) => {
      t = t.replace(re, (_, n) => {
        const valor = numeroBR(n);
        return n + " " + (valor === 1 ? singular : plural);
      });
    });

    // 3. marcador de plural "(s)" resolvido pela contagem
    t = t.replace(/\b(\d+|um|uma)\s+([A-Za-zÀ-ÿ]+)\(s\)/gi, (_, qtd, palavra) => {
      const n = /^\d+$/.test(qtd) ? parseInt(qtd, 10) : (qtd.toLowerCase() === "uma" ? 1 : 1);
      // o número por extenso entra na passagem 6; aqui só resolvemos o plural
      return qtd + " " + (n === 1 ? palavra : pluralizar(palavra));
    });
    t = t.replace(/([A-Za-zÀ-ÿ]+)\(s\)/gi, "$1");  // sem contagem: lê no singular

    // 4. tempo colado no número (15s / 2min / 1h)
    t = t.replace(/\b(\d+)\s*(?:s|seg|segs)\b/gi, (_, n) => (n === "1" ? "1 segundo" : n + " segundos"));
    t = t.replace(/\b(\d+)\s*(?:min|mins)\b/gi, (_, n) => (n === "1" ? "1 minuto" : n + " minutos"));
    t = t.replace(/\b(\d+)\s*(?:h|hs)\b/gi, (_, n) => (n === "1" ? "1 hora" : n + " horas"));

    // 5. sinais e abreviações
    t = t.replace(/%/g, " por cento ");
    t = t.replace(/\s*&\s*/g, " e ");
    ABREV.forEach(([re, troca]) => { t = t.replace(re, troca); });

    // 6. números SOLTOS ficam como estão — de propósito.
    //
    //    A tentação é escrever tudo por extenso, mas em português o numeral
    //    concorda em gênero com o substantivo: "1 vaga" é "uma vaga", "2 vagas"
    //    é "duas vagas", "200 vagas" é "duzentas vagas". Uma voz neural resolve
    //    isso sozinha (e resolve melhor do que uma tabela nossa), então converter
    //    seria trocar um acerto por um erro: "um vaga".
    //
    //    O trabalho do verbalizer é só o que a voz NÃO consegue ler: símbolo de
    //    moeda, unidade de medida, %, abreviação e marcador de plural. Número por
    //    extenso continua existindo onde o gênero é nosso e conhecido — o valor em
    //    reais (sempre masculino) e os centavos.

    // 7. faxina final
    t = t.replace(/\s+/g, " ")
      .replace(/\s+([,;.!?])/g, "$1")
      .replace(/\b(e)\s+e\b/gi, "$1")
      .trim();
    return t;
  }

  global.VVScript = {
    generate: generateScript,
    TONES,
    detectRoom,
    // verbalizer: tudo que o TTS consome passa por aqui antes de virar áudio
    verbalize,
    inteiroPorExtenso,
    reaisPorExtenso,
    pluralizar,
  };

})(window);
