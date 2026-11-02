# Editor automático das histórias (Parte 1 / Parte 2)

Monta os dois vídeos finais a partir das cenas geradas no Arkonhub, no mesmo padrão dos
vídeos de exemplo: cortes nas pausas das falas, transições (escurecer / flash branco),
com legendas em Lilita One (dá para desligar por história), trilha do Suno com ducking,
efeitos do ElevenLabs e o encerramento "Continua no Próximo episódio..." na Parte 1.

## 1. Preparar a pasta da história

```
Vídeos Historias\
  4\                      <- pasta da história (qualquer nome)
    01.mp4  02.mp4  03.mp4 ...   <- cenas numeradas, na ordem (ou dentro de uma subpasta "cenas")
    briefing.txt          <- opcional (modelo em editor\briefing_exemplo.txt)
```

Os nomes só precisam ter um número na ordem certa (`1.mp4`, `cena 2.mp4`, `03.mp4`...).

## 2. Rodar

```bash
python "C:\Users\Jorge Neves\Desktop\Vídeos Historias\editor\editar.py" "C:\Users\Jorge Neves\Desktop\Vídeos Historias\4" --estilo drama
```

Opções úteis:

| opção | o que faz |
|---|---|
| `--estilo drama` | estilo da trilha: drama, melancólico, piano, suspense, ação, épico (pastas de `Trilha sonoras 2 Facebook`; "inspiradora", "emocionante" e "leve" vão para o Piano) |
| `--briefing arquivo.txt` | usa outro briefing (padrão: `briefing.txt` dentro da pasta) |
| `--so-planejar` | só transcreve, mostra os cortes e a divisão; não renderiza |
| `--previa` (ou `--previa 20`) | renderiza só uma prévia de ~15 s do começo da Parte 1 em `PRONTO\Previa.mp4` (mostrar antes do vídeo completo) |
| `--previa 15 --previa-de 2` | prévia que começa nos últimos 5 s da cena 2 (ex.: fim da cena 2 + cartela + começo da cena 3); `--previa-cauda 4` muda os 5 s |
| `--parte 1` ou `--parte 2` | renderiza só uma das partes |
| `--forcar-transcricao` | ignora o cache de transcrições (se trocou um clipe mantendo o nome) |

Saída em `<pasta>\PRONTO\`: `Parte 1.mp4`, `Parte 2.mp4` e `relatorio.md` (cortes, trilha, efeitos).
A pasta `<pasta>\trabalho\` guarda o cache (transcrições, legendas `.ass`, quadro congelado, filtros) e pode ser apagada.

## 3. Como a edição é decidida

- **Cortes (tempo morto):** os clipes do Veo têm ~8 s, mas a fala costuma acabar antes. Como nos exemplos 2 e 3
  (medidos quadro a quadro), cada cena começa 0,2 s antes da primeira palavra e termina 0,55 s depois da última; o
  resto é descartado. Exceção: se depois da fala a imagem se mexe bem mais do que durante a fala, o editor segura até
  1,2 s a mais. Cena sem fala fica com até 8 s (`cena 7: duração 3` para encurtar). Ajuste em `config.json > cortes`.
- **Um vídeo só** (pedido do usuário em 27/10/2026): a história inteira vira `Parte 1.mp4`. Ele começa direto na
  imagem e termina com fade preto de 0,5 s.
  - **"Continua no Próximo episódio..."** só com `continua: sim` no briefing.
  - **Duas partes** só com `dividir: sim`, que divide no corte mais perto de 60 s, ou com `parte 1 até a cena: N`.
    A Parte 2 leva o resto.
- **Transições** (como nos exemplos):
  - **escurecer** (0,2 s até o preto, 0,2 s de volta) e **flash branco** (0,17 s subindo, 0,2 s descendo) se alternam;
  - **dissolve** (0,5 s, uma cena mistura na outra) entra sozinho quando a fala continua no clipe seguinte
    (a última palavra da cena não tem ponto final);
  - **luz quente / light leak** (vermelho → laranja → amarelo-branco, ~0,35 s) entra sozinha nos picos de amor e
    saudade ("eu te amo", "o lugar dela", "tarde demais"...), no máximo uma a cada 40 s;
  - por cena no briefing: `cena 5: transição flash` (escurecer, flash, dissolve, luz, corte).
  - **Som:** nenhum efeito entra sozinho (regra do usuário, 31/10/2026). Só com pedido:
    `cena N: som Flash Camera 01` ou `cena N: som Flash Camera 01 + Woosh 02` (tocam juntos). O pico do som cai na troca
    de cena (o clique, 0,14 s antes do clarão). Volume de cada um em `config.json > efeitos.niveis`.
- **Legendas:** **ligadas em todos os vídeos** desde 31/10/2026 (`legenda.ativa` no `config.json`).
  Numa história: `legenda: não` desliga e `legenda: minúsculas` troca a caixa alta. Como ficam:
  - Lilita One, 1–3 palavras por bloco, frases cortadas na pontuação, palavra atual em amarelo, na altura da história
    2 pt 1 (centro em y=1376);
  - o bloco não termina em palavra de ligação ("POR / QUE VOCÊ" vira "POSSO SABER / POR QUE VOCÊ");
  - os tempos são presos à voz medida no áudio de cada clipe (o transcritor estica as pausas); só a legenda usa isso,
    os cortes não mudam;
  - palavra errada na transcrição: `cena 2: corrigir desde por 10`;
  - cena sem fala em que o transcritor inventou uma frase no silêncio ("Obrigado por assistir."): `cena 20: sem fala`.
- **Trilha:** como nos exemplos, cada parte tem mais de uma música e cada música nova começa do início dela:
  - **abertura (gancho):** uma trilha tensa (Epic ou Suspense) nos primeiros segundos; troca para a trilha da história
    numa transição entre 15 e 32 s na Parte 1 e entre 6 e 17 s na Parte 2, de preferência na primeira cena mais
    emotiva. `trilha abertura: suspense` (ou um nome) escolhe; `trilha abertura: não` desliga;
  - **trilha da história:** escolhida pelo clima das falas de cada parte, cruzado com o `catalogo_trilhas.json`
    (medidas + descrição do Gemini). O plano mostra o porquê. `--estilo`/`estilo:` dizem a pasta preferida;
    `trilha:`, `trilha parte 2:` e `cena 7: trilha inspiradora` mandam mais que tudo;
  - **troca** (pedido do usuário em 02/11/2026): a trilha que sai termina com fade out de 1,0 s e a nova entra com a
    cena, com fade in de 0,5 s, sem sobrepor (`trilha.troca_fade_out` / `troca_fade_in`; sem essas chaves volta o
    crossfade de 1,8 s dos exemplos);
  - **número da cena = número do arquivo:** se faltar um (18, 20, 21...), `cena 20` é o arquivo 20;
  - **volume:** fala em -15 LUFS e trilha em -21,5 LUFS (~6,5 dB abaixo, como nos exemplos), com ducking leve
    (~3–4 dB) quando alguém fala. No fim de cada parte o editor mede a fala e o fundo no vídeo pronto e avisa se a
    diferença ficar abaixo de 10 dB (`trilha.diferenca_minima_db`).
  Trilha nova na pasta: entra no catálogo sozinha na próxima edição (`python trilhas.py --catalogar --gemini` refaz tudo).
- **Trilha pelo número (30/10/2026):** os arquivos da pasta nova são numerados, e **`Drama 01` = pasta Drama, trilha
  01**. Vale em `trilha:`, `cena N: trilha`, `trilha abertura:` e `trilha parte N:`. Só o nome da pasta escolhe pelo
  clima das falas. Número ou nome que não existe para a edição com um aviso. A lista completa está em
  `PROMPT_MODELO_DE_IDEIA.md`.
- **Efeito pelo número (31/10/2026):** a mesma regra das trilhas: **`Woosh 02` = pasta woosh, arquivo 02**. Só o nome da
  pasta usa o 01. Número ou efeito que não existe para a edição com um aviso. Lista em `PROMPT_MODELO_DE_IDEIA.md`.
- **Pastas (desde 27/10/2026):** trilhas só de `Desktop\Trilha sonoras 2 Facebook` (Drama, Epic, Piano, Suspense)
  e efeitos só de `Desktop\Efeitos sonoros 2`. As pastas antigas não são mais usadas, e o catálogo de trilhas só
  tem as da pasta nova.
- **Efeitos:** só os da pasta `Efeitos sonoros 2`, e só os pedidos. No encerramento:
  `encerramento: som final Flash Camera 01 + Woosh 02; som digitação Teclado Digitando 01` (passagem para o P&B e
  enquanto digita; o teclado fica alto, como nos exemplos). Pelas falas, o editor **sugere** efeitos
  (ex.: "tempestade" → Tempestade, "celular" → Celular Vibrando) e mostra no plano; eles só entram se você
  (ou o Claude) colocar no briefing: `cena 3: efeito celular vibrando em 2.0`. Para aplicar as sugestões sozinho,
  mude `efeitos.aplicar_sugestoes` para `true` no `config.json`.
- **Encerramento "Continua no Próximo episódio..."** (só com `continua: sim`; medido nos exemplos 2 e 3, ~11 s): flash branco → o resto do
  último clipe **continua andando** em preto e branco (4 s, câmera lenta se faltar imagem) com zoom de ~5%/s e giro
  anti-horário de ~1,5°/s → escurece em 0,4 s → "Continua no Próximo episódio..." em Georgia itálico amarelo
  (#EDFC00), digitado a 12 letras/s com cursor branco → segura 3,3 s → fade de 0,6 s.
  Texto e tempos em `config.json > encerramento` ou `encerramento: preto e branco 3s; segurar 6s` no briefing.
- **Câmera** (medida em 27/10/2026 comparando cada clipe original de Downloads com os vídeos editados 2 e 3;
  valores em `config.json > camera`; detalhes em `camera.py`):
  - **recorte base 1,02×** em todas as cenas; o vídeo sempre preenche o 9:16, sem tarja preta;
  - **zoom de impacto no gancho:**
    - como na 3 pt 1: na 1ª cena com exclamação ("Moço, pelo amor de Deus!"), a imagem aproxima devagar, aperta
      até 1,30× em ~2,5 s terminando na exclamação, segura 0,25 s e volta em ~3 s;
    - o zoom mira o rosto, achado pela cor da pele;
  - **zoom in lento** (como na 2 pt 2: 1,00→1,14 e 1,00→1,09, linear, na cena inteira) e **zoom out lento**
    (1,22→1,00 e ~1,35→1,00, saindo do rosto):
    - entram sozinhos em até ~25% das cenas, e só nas cenas em que a câmera do próprio clipe está parada (a
      maioria dos clipes do Veo já se aproxima sozinha);
    - in em falas tristes ou de confissão; out em alívio, pergunta ou revelação;
    - nunca dois seguidos na mesma direção;
  - **recorte fixo** (`close`, `zoom 1.13`, `zoom 1.1 cima`): a 3 pt 2 usou 1,13 para tirar da imagem a legenda
    "Toma!" que veio gravada no clipe da IA. A folha `trabalho\cenas_brutas.png`, gerada no plano, serve para achar
    esses casos;
  - **clipe horizontal** (história 2):
    - o recorte 9:16 fica no centro, ou desliza devagar e em linha reta de uma posição a outra, como os seus
      keyframes (ex.: 0,30 → 0,41 em 8 s);
    - o padrão é o centro, porque testado contra a sua edição ele erra menos que rastrear a pessoa;
    - o diretor escolhe olhando `trabalho\cenas_brutas.png`, com `cena N: enquadrar 0.3 > 0.41`,
      `enquadrar esquerda` ou `enquadrar 0.34`;
    - `enquadrar seguir` acompanha a pessoa sozinho;
    - `cena N: espelhar` inverte a imagem, para manter o olhar entre dois planos (a 2 pt 1 tem um clipe espelhado);
  - por cena no briefing: `zoom in | zoom out | zoom impacto em 3.2 | close | zoom 1.13 | sem zoom | espelhar |
    enquadrar 0.3 > 0.41`. Para desligar tudo: `camera: parada`.
- **Cartela entre cenas** (`cartela depois da cena 2: ANOS DEPOIS... | 3.5s | efeito Relógio 01 | trilha abaixa`):
  - a cena escurece até o preto (0,4 s);
  - o texto amarelo (Georgia itálico, como o "Continua...") aparece letra por letra, cada letra saindo do
    transparente e desfocado, então a revelação tem borda em degradê da esquerda para a direita;
  - durante a cartela a trilha abaixa (padrão; `trilha some` deixa só o efeito) e o efeito toca baixinho;
  - a cartela funde (0,5 s) na cena seguinte, que já entra andando e com a sua trilha começando do início;
  - valores em `config.json > cartela`.
- **Modelo de Ideia** (`PROMPT_MODELO_DE_IDEIA.md`, 28/10/2026):
  - **Cartela:** cor (`letra branca`, `#FCD100`...) e estilo (`fade in`, `fade out`, `fade`, `digitando`,
    `letra por letra`). Efeito só se pedido: `| efeito Teclado Digitando 01` (toca só enquanto digita).
  - **Som da transição:** `cena N: som relógio` ou `cena N: transição escurecer com efeito batida do coração`
    põe esse som naquela transição; sem isso, ela fica muda.
  - **Texto no final:** `texto final: TEXTO | letra amarela | fade in` liga o encerramento (flash → P&B → texto)
    com esse texto. Digitando continua sendo o padrão dos exemplos.
  - **Congelar e duração do cartão:** `encerramento: congelar; cartão 8; texto: Continua no Próximo Episódio...` para a
    imagem no último quadro da cena (P&B, giro leve e zoom in) e faz o cartão durar 8 s no total. O zoom do encerramento
    agora é por fração de pixel: numa imagem parada, o filtro antigo tremia (aspereza 0,122 contra 0,006).
  - **Zoom no rosto do personagem:** `cena N: zoom in no rosto X Y` (ou `zoom out`, `zoom impacto ... em 6.4`).
    O zoom fica preso nesse ponto, então o rosto cresce no lugar. As coordenadas saem de `trabalho\grade_cenas.png`,
    gerada no plano com o começo e o fim de cada cena e uma grade de 10%. `no rosto esquerda|direita|centro` usa o
    detector automático por cor de pele, que erra em cenário de madeira/bege.
- **Cor** (medida em YUV nas edições 2 pt 2, 3 pt 1 e 3 pt 2; `config.json > cor`): mais contraste e sombras mais
  fundas, leve tom frio, cores um pouco mais vivas e vinheta leve (cantos ~5% mais escuros).
  - Conferida renderizando os 20 clipes originais da história 3 (`editor	este_h3`) contra a edição do usuário:
    diferença menor que 1% em brilho e cor.
  - Os valores YUV do clipe passam direto, marcados como BT.709, como no editor do usuário. Sem isso o ffmpeg
    convertia de BT.601 e a imagem perdia ~10% de cor e contraste.
  Para desligar numa história: `cor: não`.
- **Monetização** (regra do usuário de 27/10/2026: entregar SEMPRE dentro das Políticas de Monetização de Conteúdo):
  - Depois de renderizar, o editor roda o `monetizacao.py`, que confere:
    - **Seção 1:** vídeo parado, slideshow, loop, montagem de texto, anúncio;
    - **Seção 2:** isca de engajamento, venda de envolvimento;
    - **Seções 3 e 4:** pelas falas, linguagem ofensiva, sexual, drogas e crimes, explícito, polêmica, tragédia,
      desinformação e alegação médica;
    - originalidade do áudio, formato Reel e trilha abaixo da fala.
  - Ele grava `PRONTO\checklist_monetizacao.md` e as folhas de quadros para a revisão visual (`trabalho\folha_parteN.png`,
    `cantos_parteN.png`).
  - Correções no briefing: `cena N: silenciar <palavra>`, `cena N: fim X`, `cena N: remover`, `cena N: zoom 1.13`.
  - Detalhes em `POLITICAS_FACEBOOK.md`.

## 4. Transcrição

Usa a chave Groq já configurada em `~/.config/watch/.env` (rápida). Sem chave, usa o faster-whisper local
(`--modelo-local large-v3-turbo` para mais precisão; mais lento).

## 5. Fonte das legendas

Padrão: **Lilita One** (Google Fonts, licença OFL), que fica em `editor\fonts\LilitaOne-Regular.ttf` e é a
mais parecida com a fonte dos exemplos; tamanho 92 dá a mesma altura de letra (55 px). O itálico é inclinação
sintética, como nos exemplos. Para usar outra fonte, coloque o `.ttf` em `editor\fonts\` e mude `legenda.fonte`
para o nome da família (sem a pasta de fontes, a Segoe UI Black Itálico do Windows em tamanho 105 é a melhor opção).
