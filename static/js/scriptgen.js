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
      tone: tone.label,
      targetSeconds: total,
      wordCount: words,
      readSeconds: Math.round((words / 150) * 60),
    };
  }

  global.VVScript = { generate: generateScript, TONES, detectRoom };

})(window);
