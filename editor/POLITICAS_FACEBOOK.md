# Monetização do Facebook: checklist obrigatório de TODO vídeo pronto

**Regra do usuário (27/10/2026):** todo vídeo que eu terminar é entregue **já dentro das Políticas de Monetização
de Conteúdo**, junto com o checklist preenchido. Se algum item der ❌, eu corrijo a edição (corto, silencio, troco
ou removo a cena) e renderizo de novo **antes** de entregar. Nunca entrego um vídeo com ❌ ou com 👁 pendente.

Bases (em `editor\referencias\`):

- `Politicas-de-Monetizacao-de-Conteudo-CMP.pdf`: guia da Meta, de 26/10/2026. É a base principal.
- `Politicas_Monetizacao_Facebook_Premium_4.pdf`: Parceiro (PMP), originalidade e Padrões da Comunidade.
- `Guia-Verdade-ou-Mito-Monetizacao-Facebook.pdf`: dicas de postagem.

Para monetizar, o conteúdo precisa passar por três camadas ao mesmo tempo:

1. Padrões da Comunidade.
2. Políticas para Parceiros (PMP).
3. Políticas de Monetização de Conteúdo (CMP), aplicadas a cada vídeo.

Um vídeo permitido no Facebook **não é necessariamente monetizável**.

## Como funciona

1. **Automático.** O `editar.py` roda o `monetizacao.py` depois de renderizar as partes. Ele:
   - lê todas as falas que ficaram no vídeo;
   - mede o movimento de cada cena e compara as cenas entre si (loop);
   - confere o formato do arquivo, as pastas de trilha e efeitos e o nível da trilha;
   - grava `PRONTO\checklist_monetizacao.md`, com ✅ ok, ⚠️ atenção (explicado), ❌ corrigir antes de publicar e
     👁 falta revisão visual.
2. **Revisão visual (eu, Claude).** Para cada parte:
   - olho `trabalho\folha_parteN.png` (1 quadro a cada 2 s) e `trabalho\cantos_parteN.png` (cantos a cada 4 s,
     para marca d'água);
   - leio a transcrição inteira no `relatorio.md`;
   - gravo `trabalho\revisao_visual.json`:
     ```json
     {"1": {"sexual": "ok", "explicito": "ok", "criancas": "ok", "marca_dagua": "ok", "construtivo": "ok",
            "desinformacao": "ok", "nota": "o que eu conferi"},
      "2": {...}}
     ```
     Um valor diferente de `"ok"` vira ❌, com esse texto como motivo.
   - depois rodo `python editor\monetizacao.py "<pasta da história>"`. Ele regrava o checklist e retorna o código 1
     enquanto houver ❌.
3. **Corrigir, se preciso, e repetir.** Use as instruções do briefing abaixo e renderize de novo.
4. **Entregar** o vídeo com o resumo do checklist: tudo ✅, ou ⚠️ com a explicação.

## Checklist (as seções do PDF da Meta)

### Seção 1: formatos proibidos (não monetiza)

| Item | Como confiro | Correção |
|---|---|---|
| Vídeo estático (imagem parada, pouco ou nenhum movimento) | movimento medido por cena no vídeo pronto | trocar o clipe ou `cena N: remover` |
| Enquete de imagem estática | é sempre vídeo | - |
| Apresentação de imagens (slideshow) | toda cena é clipe com movimento real | idem |
| Vídeo em loop (mesmo trecho repetido, GIF) | mesmo arquivo em duas cenas, ou cenas quase idênticas | não repetir clipe |
| Montagem de texto (texto como elemento principal) | legendas só acompanhando a fala; cartão final < 20% do vídeo | `encerramento: segurar 2` |
| Anúncio incorporado (pre-, mid- ou post-roll, banner) | o editor nunca insere | - |

### Seção 2: comportamentos proibidos

| Item | Como confiro | Correção |
|---|---|---|
| Isca de engajamento: pedir curtida, comentário, compartilhamento ou clique ("comente amém", "compartilhe com quem você ama", "marque alguém", "link na bio", "digite sim") | léxico nas falas | `cena N: fim X` para cortar a frase, ou `cena N: silenciar <palavras>` |
| Venda de envolvimento (recompensa por comportamento extremo) | léxico nas falas | cortar |
| Convite para seguir a página | não está na lista de isca do CMP | fica **uma vez**, curto, no fim da Parte 2 (como nos exemplos) |

Pergunta para o público sem pedir comentário ("E você? Quem você gostaria de encontrar lá?") é permitida.

### Seção 3: categorias restritas (reduz ou desativa a monetização, mesmo em ficção)

| Item | Como confiro | Correção |
|---|---|---|
| Temas sociais polêmicos (raça, religião, política, imigração...) com tom polarizado | léxico + leitura | tirar o tom provocador ou cortar |
| Tragédia ou conflito (morte, doença, abuso) | léxico anota o tema e eu confirmo que é **construtivo** (superação, amor, reconciliação), sem sensacionalismo | reescrever ou cortar a fala sensacionalista |
| Atividade censurável (drogas, álcool, crimes, armas) | léxico + imagem | só passa se aparece como errado, sem glorificar e sem mostrar o uso |
| Sexual ou sugestivo (nudez, poses, roupa reveladora, linguagem) | léxico + **folha de quadros** | cortar a cena ou trocar o clipe |
| Linguagem ofensiva (palavrão, insulto, termo depreciativo, gesto obsceno) | léxico (palavrão = ❌) | `cena N: silenciar <palavra>` |
| Conteúdo explícito (sangue, ferida, vômito, funções corporais) | léxico + **folha de quadros** | cortar |

### Seção 4: categorias proibidas (nunca monetiza)

| Item | Como confiro | Correção |
|---|---|---|
| Desinformação | não apresentar ficção feita com IA como "história real" ou "aconteceu de verdade" | cortar a frase |
| Informação médica enganosa (cura milagrosa, antivacina, "não precisa de remédio") | léxico | cortar |

### Parceiro (PMP) e IA (não estão no PDF do CMP, mas valem para a página)

| Item | Como confiro |
|---|---|
| Originalidade e áudio | História, imagens (Flow), cenas (Arkonhub/Veo) e edição são do usuário. Trilhas do **Suno** e efeitos do **ElevenLabs** foram criados do zero pelo usuário: áudio original. O checklist confere que só as pastas `Trilha sonoras 2 Facebook` e `Efeitos sonoros 2` foram usadas. Lembrete: plano pago do Suno/ElevenLabs (direito de uso comercial) e trilhas **não** enviadas a distribuidoras (DistroKid, ONErpm), que registram no Content ID e geram claim nos próprios vídeos. |
| Marca d'água, logo ou texto de terceiros | `cantos_parteN.png` + `trabalho\cenas_brutas.png` (texto gravado pela IA, como o "Toma!" da história 3). Correção: `cena N: zoom 1.13` (ou `zoom 1.1 cima`). |
| Crianças | tolerância zero: nenhuma criança exposta, vulnerável, com roupa inadequada ou em risco |
| Técnico | 1080x1920, 30 fps, com áudio, publicado como **Reel** |
| Rótulo de IA | ao publicar, marcar **"Informações de IA" / conteúdo criado com IA** |

## Consequências e apelação (Seção 5 do PDF)

- Um vídeo que viola o CMP deixa de gerar receita. Violações repetidas podem bloquear as ferramentas de monetização
  da página, de forma temporária ou permanente.
- Onde conferir: Meta Business Suite › Monetização (computador) ou Painel profissional (celular).
- Apelação: pelo formulário das Políticas de Monetização. Cada item aceita uma apelação, em geral analisada em até 7 dias.

## Postagem (do Guia Verdade ou Mito)

- 1 a 2 vídeos por dia, espaçados: Parte 1 e Parte 2 separadas por algumas horas. O gancho "Continua no Próximo
  episódio..." só vale se a Parte 2 existir e cumprir o que promete.
- Título e texto do post sem pedir curtida, comentário ou compartilhamento e sem exagerar o que acontece.
- 0 a 3 hashtags do nicho. Nas primeiras semanas, postar manualmente e responder os comentários nos primeiros 15–30 min.
- Sem compra de seguidores ou views e sem compartilhamento em massa combinado.
- As regras mudam: na dúvida, confirmar em facebook.com/business/help/1348682518563619.
