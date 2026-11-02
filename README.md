# Skill historia-fb: edição das histórias do Facebook

Pacote completo da skill de edição: o editor automático, as trilhas sonoras, os efeitos sonoros, os vídeos de
referência e os briefings aprovados. É uma cópia da pasta `Desktop\Vídeos Historias` com as pastas de trilhas e
efeitos do Desktop. Ficaram de fora as cenas brutas, os arquivos de trabalho e os kits de teste do editor.

## O que tem aqui

| Pasta / arquivo | O que é |
|---|---|
| `.claude/skills/historia-fb/SKILL.md` | A skill: como o Claude dirige e edita cada história (regras do usuário, fluxo, prévia, monetização). |
| `editor/` | O editor: `editar.py`, `camera.py`, `monetizacao.py`, `trilhas.py`, `config.json` (estilo medido nos exemplos), `catalogo_trilhas.json`, a fonte Lilita One e os guias `COMO_USAR.md`, `POLITICAS_FACEBOOK.md` e `briefing_exemplo.txt`. |
| `editor/referencias/` | PDFs das Políticas de Monetização de Conteúdo (CMP) do Facebook usados no checklist. |
| `PROMPT_MODELO_DE_IDEIA.md` | O Modelo de Ideia para pedir um vídeo, com a lista do que cada trilha numerada toca. |
| `PROMPT_BASE.md` | O prompt base completo, com todo o vocabulário de direção. |
| `Trilha sonoras 2 Facebook/` | As 13 trilhas (Suno), numeradas: Drama 01–04, Epic 01–05, Piano 01–02, Suspense 01–02. "Drama 01" = pasta Drama, arquivo 01. |
| `Efeitos sonoros 2/` | Os efeitos (ElevenLabs), numerados: Batida de Coração 01–02, Celular Vibrando 01, Click de Mouse 01, Flash Camera 01, Relógio 01, Teclado Digitando 01, Woosh 01–02. |
| `1/`, `2/`, `3/` | Vídeos de referência de estilo (Parte 1 e Parte 2 de cada história), medidos quadro a quadro para o `config.json`. |
| `4/` | As edições aprovadas pelo usuário: `pt 1/1.mp4` (o primeiro salário) e `pt 2/2.mp4` (os 800 reais guardados). |
| `Hist 1/`, `Hist 1 pt 1/`, `Hist 1 pt 2/` | Os briefings aprovados e o que foi entregue com cada vídeo (checklist de monetização, relatório e texto do post). |

Os vídeos (`.mp4`) estão no **Git LFS**. Para baixar tudo, instale o Git LFS antes de clonar:

```bash
git lfs install
git clone https://github.com/avilajorginho335/skill-historias-facebook.git
```

## Usar em outro computador

1. Copie as pastas para os mesmos lugares (`Desktop\Vídeos Historias`, `Desktop\Trilha sonoras 2 Facebook` e
   `Desktop\Efeitos sonoros 2`). Se usar outro lugar, troque `trilha.pasta` e `efeitos.pasta` em `editor/config.json`.
2. Instale Python 3 com `numpy` e o `ffmpeg` (com `ffprobe`) no PATH.
3. Coloque a chave do Groq (`GROQ_API_KEY=...`) em `~/.config/watch/.env` ou em `editor/.env`. Sem chave, o editor
   transcreve com o faster-whisper local, que é mais lento. As chaves nunca vão para este repositório.
4. Abra a pasta `Vídeos Historias` no Claude Code: a skill `historia-fb` é carregada de `.claude/skills/`.

Como editar uma história (planejar, prévia, vídeo final, checklist): `editor/COMO_USAR.md` e o próprio `SKILL.md`.
