---
name: historia-fb
description: Edição automática das histórias do Facebook do usuário (Parte 1 e Parte 2) com editor/editar.py, no padrão medido dos exemplos 2 e 3 (câmera com zoom in/out/impacto, cor, transições com som, trilhas, encerramento) e sempre entregue dentro das Políticas de Monetização de Conteúdo. Use quando o usuário mandar uma nova história para editar — o Modelo de Ideia (PROMPT_MODELO_DE_IDEIA.md: "Da cena 01 à 02 use uma trilha de...", texto na transição com cor e estilo, efeito sonoro, texto no final), o prompt base (PROMPT_BASE.md, "PAPEL Atue como diretor...", "EDITAR HISTÓRIA:"), a ideia/estilo do vídeo (drama, suspense, emocionante...) e a pasta com as cenas numeradas do Arkonhub/Flow —, pedir para "montar a história", "fazer a parte 1 e parte 2", "juntar as cenas", ajustar cortes/zoom/legendas/trilha/efeitos de uma edição, revisar monetização de um vídeo, ou perguntar como funciona o editor. Não confundir com o skill /editar (Reels com editonny).
---

# Edição das histórias (Parte 1 / Parte 2)

Fale em português do Brasil. Trabalhe como **diretor de vídeo e audiovisual, roteirista e editor profissional**: leia
a história inteira, entenda o arco (gancho → virada → emoção → fecho) e só então decida câmera, transições, trilha e
efeitos.

Pastas fixas:

- **Editor:** `C:\Users\Jorge Neves\Desktop\Vídeos Historias\editor\`
  - programas: `editar.py`, `camera.py`, `monetizacao.py`, `trilhas.py`
  - regras e modelos: `config.json`, `COMO_USAR.md`, `POLITICAS_FACEBOOK.md`, `briefing_exemplo.txt`
- **Prompts do usuário:**
  - `Vídeos Historias\PROMPT_MODELO_DE_IDEIA.md` (o mais usado): trilha por trecho de cenas; transição com texto
    (fundo preto, cor, estilo) e/ou efeito sonoro; texto final; estilo da história.
  - `Vídeos Historias\PROMPT_BASE.md`: a versão completa, com todo o vocabulário de direção.
  - Tradução para o briefing:
    - "da cena 1 à 2: Suspense 02" → `trilha: Suspense 02` (ou `cena 1: trilha Suspense 02`); "cena 3: Drama 03" →
      `cena 3: trilha Drama 03`; sem número ("Drama") → `cena 3: trilha drama` (escolhe pelo clima);
    - texto na transição → `cartela depois da cena N: TEXTO | letra COR | ESTILO | Xs | efeito EFEITO | trilha abaixa`;
    - efeito na transição → `cena N: som EFEITO` (vários: `som Flash Camera 01 + Woosh 02`, tocam juntos);
    - efeitos do final → no `encerramento:`, `som final Flash Camera 01 + Woosh 02` (passagem para o P&B) e
      `som digitação Teclado Digitando 01` (só enquanto digita);
    - final → `texto final: TEXTO | letra COR | ESTILO` (sem texto = fade para o preto);
    - "congele a tela em P&B com leve rotação e zoom in" + cartão de X s → `continua: sim` e
      `encerramento: congelar; cartão X; texto: TEXTO` (o texto por último; sem "congelar" a cena segue andando);
    - o Modelo termina com "Estruture o prompt para mim": se vieram as cenas, entregue o prompt estruturado E a
      prévia com todas as cenas (não pare só no prompt);
    - "zoom in/out no rosto do personagem [descrição]" → abra `trabalho\grade_cenas.png`, gerada no plano, com o
      começo e o fim de cada cena e uma grade de 10%. Ache o rosto dessa pessoa: no FIM para zoom in, no COMEÇO
      para zoom out. Escreva `cena N: zoom in no rosto X Y` (ex.: `zoom in no rosto 0.52 0.30`). Para um trecho
      ("da cena 1 à 2"), escreva uma linha por cena;
    - o detector automático por cor de pele erra em cenário de madeira/bege: use sempre coordenadas;
    - se o clipe já se aproxima sozinho do rosto (o começo e o fim da grade mudam muito), avise o usuário: o zoom
      de edição quase não aparece.
- **Prompt base do usuário:** `C:\Users\Jorge Neves\Desktop\Vídeos Historias\PROMPT_BASE.md`. Quando ele mandar
  esse prompt preenchido, converta cada campo em `briefing.txt` (vocabulário na tabela do próprio arquivo).
- **Trilhas (Suno):** `C:\Users\Jorge Neves\Desktop\Trilha sonoras 2 Facebook\`, com as pastas Drama, Epic,
  Piano e Suspense: 13 trilhas numeradas, as mesmas referências dos exemplos.
  **Regra do usuário (30/10/2026): "Drama 01" = pasta Drama, trilha 01; vale para todas as pastas e trilhas.** A lista
  com o que cada número toca está em `PROMPT_MODELO_DE_IDEIA.md`. Só o nome da pasta = você escolhe a melhor dela.
- **Efeitos (ElevenLabs):** `C:\Users\Jorge Neves\Desktop\Efeitos sonoros 2\`, com batida de Coração, Celular
  Vibrando, Click de Mouse, Flash Camera, Relogio, teclado digitando e woosh, com arquivos numerados.
  **"Woosh 02" = pasta woosh, arquivo 02** (31/10/2026, mesma regra das trilhas); só a pasta = arquivo 01; número que não
  existe para com aviso. Woosh 01 é o suave, Woosh 02 é o WOOSH BOOM. No briefing:
  `cena N: som Woosh 02`, `cena N: efeito Batida de Coração 02 em 6.15`, `cartela ... | efeito Relógio 01`.
- **Troca de pastas (27/10/2026):** o usuário restringiu as referências a essas duas pastas, para não haver
  confusão. As antigas (`Trilhas sonoras`, `Efeitos sonoros`) NÃO são mais usadas. O estilo de edição não muda.
- **Histórias:** `C:\Users\Jorge Neves\Desktop\Vídeos Historias\<nome>\`, com as cenas numeradas.

Regras do usuário:

- Use SOMENTE essas trilhas e efeitos. Nunca baixe nem gere outros.
- **Efeito sonoro SÓ quando ele mandar** (31/10/2026: "retire esse barulho de woosh das transições, só deve colocar
  algum efeito sonoro quando eu mandar"). Sem pedido, nenhuma transição, cartela ou encerramento tem efeito, e você
  não acrescenta efeito por conta própria como diretor. Trilha continua sendo você quem escolhe, se ele deixar.
- **Com legendas em todos os vídeos** (pedido de 31/10/2026; substitui o "sem legendas" de 26/10). Só desligue com
  `legenda: não` se ele pedir. São em Lilita One, caixa alta, palavra atual em amarelo, na altura da história 2 pt 1.
  Antes de renderizar, leia cada palavra do plano: a
  legenda mostra o que o transcritor entendeu. Erro → `cena N: corrigir desde por 10`. Na dúvida, compare com outro
  modelo do Groq. Depois do render, confira `trabalho\legendas_parte1.ass` e uma folha de quadros.
  Cena sem voz no áudio com frase transcrita (o Whisper inventa "Obrigado por assistir." no silêncio) → `cena N: sem fala`.
- **Troca de trilha** (02/11/2026): a que sai termina com fade out de 1,0 s e a nova entra com fade in de 0,5 s (já é o
  padrão do `config.json`). O número da cena é o número do arquivo, mesmo com um faltando.
- **"Adicione efeitos sonoros" sem dizer quais** = você escolhe, poucos e nos pontos-chave. Referência aprovada em
  02/11/2026 ("ficou ótimo"): `Hist 1 pt 2\briefing.txt`, com Woosh 02 no fim da briga, Relógio 01 sutil na cartela,
  Flash Camera 01 no flash da revelação, Batida de Coração 02 numa pausa e Woosh 01 na luz quente. Nunca em toda transição.
- **Um vídeo só** (pedido de 27/10/2026): cada história vira só a Parte 1, com todas as cenas. Divida em Parte 1 /
  Parte 2 apenas se ele pedir (`dividir: sim` ou `parte 1 até a cena: N` no briefing).
- **"Continua no Próximo episódio..." só quando ele pedir** (`continua: sim` no briefing). Sem pedido, o vídeo
  termina com fade para o preto e não tem o encerramento flash → P&B → texto.
- Valores de estilo ficam no `config.json`: mude lá, não no código.

**Referência de estilo:** `Vídeos Historias\2\pt 1`, `2\pt 2`, `3\pt 1` e `3\pt 2`. Em 27/10/2026 elas foram
medidas contra os clipes ORIGINAIS achados em Downloads, comparando zoom, recorte, cor, transições e áudio quadro a
quadro. O resumo está em `COMO_USAR.md`, seção 3, e no topo de `camera.py`. O usuário quer edições **idênticas** a
essas.

## Regras obrigatórias

1. **Prévia antes do vídeo principal** (26/10/2026). Nunca renderize a Parte 1 / Parte 2 sem antes mostrar uma
   prévia de ~15 s (`--previa`) e receber o OK. Se ele pedir mudanças, ajuste o briefing e mostre outra prévia.
2. **Entregar SEMPRE dentro das Políticas de Monetização de Conteúdo** (27/10/2026). Todo vídeo completo passa
   pelo checklist de `editor\POLITICAS_FACEBOOK.md`, baseado em
   `editor\referencias\Politicas-de-Monetizacao-de-Conteudo-CMP.pdf`. O editor gera a parte automática; você faz a
   revisão visual e completa `PRONTO\checklist_monetizacao.md`.
   - Se aparecer ❌, **corrija e renderize de novo antes de entregar**: corte a frase, silencie, troque o
     enquadramento ou remova a cena.
   - Nunca entregue com ❌ ou 👁.
   - Se a correção mudar a história (a cena-chave é o problema), explique e peça ao usuário para regerar a cena.
   - As trilhas (Suno) e os efeitos (ElevenLabs) foram criados do zero pelo usuário: são áudio original.

## Fluxo quando chega uma história

1. **Entender o pedido** (prompt base ou ideia solta).
   - Descubra a pasta das cenas. Se os clipes vieram pelo chat, copie-os para `Vídeos Historias\<nome>\` como
     `01.mp4, 02.mp4...`, na ordem.
   - Leia as falas (o plano transcreve) como roteirista: onde está o gancho, a virada, o ápice emocional e o fecho.
2. **Escrever o `briefing.txt`** na pasta da história (modelo em `briefing_exemplo.txt`). Coloque:
   - `estilo:`;
   - `continua: sim` só se ele pedir o "Continua no Próximo episódio..."; `dividir: sim` / `parte 1 até a cena: N`
     só se ele pedir duas partes;
   - as instruções por cena que o usuário pediu ou que você, como diretor, decidir.
   Sem instruções, só `estilo:` basta: o resto é automático.
3. **Planejar** (rápido; mostra cortes, divisão, transições, câmera e trilha):
   ```bash
   cd "C:\Users\Jorge Neves\Desktop\Vídeos Historias\editor" && PYTHONIOENCODING=utf-8 python editar.py "<pasta da história>" --so-planejar
   ```
   Revise como diretor:
   - **Cortes:** os clipes do Veo têm ~8 s e a fala acaba antes. O plano mostra quanto tempo morto foi aparado.
     Se uma cena precisa do fim (uma saída, um olhar), use `cena N: sem corte` ou `cena N: fim 7.5`.
   - **Folha das cenas originais:** abra `trabalho\cenas_brutas.png` (Read). Procure texto, legenda ou marca
     gravados pela IA na imagem. Na história 3 um clipe veio com "Toma!" escrito e o usuário deu zoom 1,13 para tirar.
     Corrija com `cena N: zoom 1.13` ou `cena N: zoom 1.1 cima`.
   - **Câmera** (linha "Câmera:"):
     - automático: recorte base de 1,02×;
     - automático: **zoom de impacto** na exclamação da 1ª cena (gancho);
     - automático: **zoom in/out lento e linear** em ~25% das cenas, só onde a câmera do próprio clipe está
       parada (in = fala triste ou confissão; out = alívio, pergunta, revelação);
     - clipes horizontais ficam com o recorte 9:16 no centro. Olhe a folha e decida o enquadramento como na
       história 2: `cena N: enquadrar 0.34` (fixo), `enquadrar 0.3 > 0.41` (deslize lento) ou `enquadrar seguir`;
     - à mão, onde a história pedir: `cena N: zoom in|zoom out|zoom impacto em 3.2|close|espelhar|sem zoom|enquadrar 0.3 > 0.41`.
       Não empilhe zoom de edição em clipe que já tem aproximação de câmera.
   - **Transições:**
     - **flash** logo depois de fala de impacto ou revelação;
     - **luz** no ápice de amor ou saudade, ou quando uma porta se abre e revela alguém;
     - **escurecer** para passagem de tempo ou troca de lugar;
     - **dissolve** quando a frase continua no clipe seguinte.
     Ajuste com `cena N: transição ...`. As transições são só imagem: som, só se ele mandar.
   - **Trilha: você é o diretor musical.**
     - Cada parte abre com uma trilha tensa (Epic/Suspense) e troca para a da história numa transição. Toda trilha
       nova começa do início.
     - A troca caiu na virada certa? A história vira de novo mais tarde? Marque `cena N: trilha piano`.
     - Nos exemplos a música muda de 2 a 5 vezes por parte.
   - **Efeitos:** só os que ele mandou. O plano ainda lista sugestões pelas falas, mas elas não entram sozinhas e você
     não as coloca sem ele pedir.
   - **Monetização já no plano:**
     - leia as falas procurando isca ("comente", "compartilhe", "marque"), palavrão, "história real" e alegação
       médica;
     - corrija com `cena N: fim X`, `cena N: silenciar <palavra>` ou `cena N: remover`;
     - "siga a nossa página" fica uma vez, no fim.
   - **Cartela** (passagem de tempo): `cartela depois da cena N: TEXTO | 3s | efeito Pasta/arquivo | trilha some`.
     A trilha da cena seguinte (`cena N+1: trilha X`) entra junto com a cena, do início da música.
   - **"Continua" sem Parte 2:** se ele pedir o "Continua no Próximo episódio..." numa história que só tem uma
     parte, avise que ele só deve ser publicado quando a continuação existir (senão vira isca de clique).
4. **Prévia (~15 s) e OK do usuário:**
   ```bash
   cd "C:\Users\Jorge Neves\Desktop\Vídeos Historias\editor" && PYTHONIOENCODING=utf-8 python editar.py "<pasta da história>" --previa
   ```
   **História curta (poucas cenas): a prévia é o vídeo montado inteiro, com TODAS as cenas** (o usuário reclamou em
   27/10/2026 de receber só um trecho). Renderize com `--briefing` e `--saida "<pasta>\PRONTO\Versao A"`. Se ele
   pedir duas prévias, faça duas versões realmente diferentes: trilhas, efeito da cartela e transição.
   **Referência aprovada mais recente (31/10/2026, "é desse jeito mesmo que eu quero"):** `Vídeos Historias\Hist 1 pt 1`,
   vídeo `PRONTO\Parte 1.mp4` e `briefing.txt`: o que ele pediu no Modelo de Ideia (trilha e efeitos só onde mandou), mais
   as decisões de direção que ele aprovou: dissolve e escurecer nas outras transições, sem som; zoom de impacto na
   exclamação; zoom in lento até o rosto onde a imagem congela. A legenda, pedida nesse vídeo, virou padrão de todos.
   **Estilo aprovado (27/10/2026, Hist 1, versão B — "é esse o estilo, mantenha nas próximas"):**
   - abertura: Suspense 02;
   - depois da virada ou da cartela: Drama 03 (violino solo);
   - clímax: Suspense 01 (cordas em ostinato + impacto grave);
   - cartela de 3,5 s com a trilha só abaixando (padrão do `config.json`);
   - troca entre personagens na mesma cena em dissolve;
   - efeitos só se ele mandar (naquela versão ele pediu Relógio 01 na cartela e aprovou Batida de Coração 02 no clímax;
     em 31/10 mandou tirar o woosh das transições).
   Modelo pronto, já com as pastas novas: `Vídeos Historias\Hist 1\briefing.txt` (sem os efeitos dele, se não forem pedidos). Comece cada história por essa linha; varie as trilhas
   só se o clima pedir, e sempre dentro de Suspense/Drama/Piano.
   Gosto dele: violão e pop soam como "música de comercial" (por isso saíram da pasta nova); nas viradas emotivas
   use Drama ou Piano. Efeito de cartela sutil (pico -20, abaixo da fala).
   Se o usuário pedir um trecho específico (ex.: "fim da cena 2 + cartela + começo da cena 3"), use
   `--previa 15 --previa-de 2`. Ela leva a mesma câmera e a mesma música que o vídeo completo terá naquele trecho.
   Mande `PRONTO\Previa.mp4` com `SendUserFile` e diga:
   - qual trilha tocou e por quê;
   - a câmera (zoom de impacto, zooms lentos);
   - os efeitos;
   - a conferência do áudio.
   **Pare e espere o OK.**
5. **Renderizar** (2–5 min; rode em segundo plano), só depois do OK:
   ```bash
   cd "C:\Users\Jorge Neves\Desktop\Vídeos Historias\editor" && PYTHONIOENCODING=utf-8 python editar.py "<pasta da história>"
   ```
   O fim do log traz o checklist automático de monetização.
6. **Conferir o vídeo:**
   - duração das partes (`ffprobe`);
   - `trabalho\folha_parte1.png` e `folha_parte2.png`: transições, zooms e encerramento;
   - `relatorio.md`, que tem a coluna da câmera por cena;
   - a linha "conferência do áudio" deve mostrar a fala ≥ 10 dB acima do fundo. Se não, baixe `trilha.lufs`.
7. **Checklist de monetização** (regra obrigatória):
   - Olhe `trabalho\folha_parteN.png` e `trabalho\cantos_parteN.png` de cada parte e leia as falas.
   - Grave `trabalho\revisao_visual.json` com `sexual`, `explicito`, `criancas`, `marca_dagua`, `construtivo`,
     `desinformacao` (`"ok"` ou o problema) e uma `nota`.
   - Rode `python editor\monetizacao.py "<pasta>"`.
   - Enquanto houver ❌: corrija no briefing, renderize de novo a parte (`--parte N`) e repita.
8. **Entregar:** `SendUserFile` com `PRONTO\Parte 1.mp4` (e `Parte 2.mp4`, se ele pediu duas partes), mais um resumo curto com:
   - duração (e onde foi a divisão, se houver);
   - trilhas e trocas;
   - câmera e efeitos;
   - **checklist de monetização** (tudo ✅, ou ⚠️ explicado);
   - lembretes: publicar como Reel, com o rótulo de IA (e, se houver Parte 2, algumas horas depois da Parte 1).

   Se o prompt pedir, inclua o texto do post: título e 2 linhas sem isca, até 3 hashtags.

## Ajustes comuns

- **Cortes muito justos ou largos:** `config.json > cortes`, ou `cena N: sem corte` / `cena N: fim 6.5`.
- **Câmera:**
  - para tudo: `camera: parada` no briefing;
  - por cena: `sem zoom`;
  - intensidades: `config.json > camera` (zoom_in, zoom_out, impacto, fracao_zoom_lento).
- **Cor:** `cor: não` no briefing ou `config.json > cor.ativa`.
- **Trilha específica:** `trilha: <parte do nome do arquivo>` ou `cena N: trilha <nome>`.
- **Encerramento:** `encerramento: preto e branco 3s; segurar 6s`.
- **Sem Groq** (erro de rede): o script cai para o faster-whisper local, que é mais lento.
