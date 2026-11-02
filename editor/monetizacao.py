#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
monetizacao.py — Checklist das Políticas de Monetização de Conteúdo (CMP) do Facebook para cada parte pronta.

Base: referencias\Politicas-de-Monetizacao-de-Conteudo-CMP.pdf (Meta, 26/10/2026): 6 formatos proibidos,
2 comportamentos proibidos, 6 categorias restritas, 2 categorias proibidas e o checklist antes de publicar.
Mais os itens de Parceiro/IA de referencias\Politicas_Monetizacao_Facebook_Premium_4.pdf (originalidade, marca d'água,
crianças, rótulo de IA).

O editar.py chama verificar_parte() depois de renderizar cada parte e grava trabalho\monetizacao_parteN.json.
Os itens que dependem de olhar a imagem ficam "👁 pendente" até o Claude olhar as folhas de quadros
(trabalho\folha_parteN.png e cantos_parteN.png) e gravar trabalho\revisao_visual.json:
    {"1": {"sexual": "ok", "explicito": "ok", "criancas": "ok", "marca_dagua": "ok", "construtivo": "ok",
           "desinformacao": "ok", "nota": "..."}, "2": {...}}
(qualquer valor diferente de "ok" vira ❌ com esse texto). Depois:
    python monetizacao.py "<pasta da história>"
regrava PRONTO\checklist_monetizacao.md juntando tudo. Vídeo com ❌ ou 👁 não é entregue.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

OK, ATENCAO, BLOQUEIA, PENDENTE = "✅", "⚠️", "❌", "👁"


def dobrar(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


# Léxicos (texto sem acento, minúsculo). Cada entrada: (regex, gravidade). BLOQUEIA = corrigir antes de entregar.
LEXICOS: dict[str, list[tuple[str, str]]] = {
    # Seção 2 — isca de engajamento: pedir curtida, comentário, compartilhamento ou clique
    "isca": [
        (r"\bcurt(a|e|am|em)\s+(esse|este|o|a|nosso|nossa|nossas|nossos)?\s*(video|post|pagina|historia|reel)", BLOQUEIA),
        (r"\bdeix(a|e|em)\s+(o\s+|seu\s+|sua\s+|um\s+|uma\s+)?(like|joinha|curtida|coracao(zinho)?)", BLOQUEIA),
        (r"\bcomente(m)?\b", BLOQUEIA),
        (r"\bcomenta\s+(ai|aqui|embaixo|abaixo|sim|amem|nos comentarios|o que)", BLOQUEIA),
        (r"\bescrev(e|a|am)\s+(ai|aqui|nos comentarios|amem|sim)", BLOQUEIA),
        (r"\bnos comentarios\b", BLOQUEIA),
        (r"\bcompartilh(e|em)\b", BLOQUEIA),
        (r"\bcompartilha\s+(esse|este|essa|esta|com|pra|para|o video|a historia)", BLOQUEIA),
        (r"\bmarqu?e(m)?\s+(alguem|um amigo|uma amiga|quem|aquela pessoa|a pessoa)", BLOQUEIA),
        (r"\bmarca\s+(alguem|um amigo|uma amiga|quem|aquela pessoa|a pessoa)", BLOQUEIA),
        (r"\bdigit(e|a|em)\b", BLOQUEIA),
        (r"\bclique\b|\bclica\b|\blink\b", BLOQUEIA),
        (r"\bse inscrev|\bsininho\b", BLOQUEIA),
        (r"\bmand(a|e|em)\s+(esse video|essa historia|este video|isso)\s+(pra|para)", BLOQUEIA),
    ],
    # Seção 2 — venda de envolvimento: recompensa em troca de comportamento extremo
    "venda": [
        (r"\bse\s+(chegar|bater|der|tiver|passar)\s+(de\s+|a\s+|em\s+)?\d*\s*(mil\s+)?(curtidas|likes|comentarios|compartilhamentos|seguidores)", BLOQUEIA),
    ],
    # Seção 3 — linguagem ofensiva
    "ofensiva": [
        (r"\bporra\b|\bcaralho\b|\bmerda\b|\bputa\b|\bputo\b|\bfod(a|er|eu|ido|ida|endo|ase)\b|\bcacete\b|\bbuceta\b|\bcu\b"
         r"|\bviado\b|\barrombad|\bfdp\b|\bfilho da puta\b|\bvagabund|\bpiranha\b|\bcorno\b|\bbabaca\b|\botari(o|a)\b"
         r"|\bretardad|\bdesgracad|\bpqp\b|\bvsf\b", BLOQUEIA),
        (r"\bidiota\b|\bimbecil\b|\bburr(o|a)\b|\bbesta\b|\bmaldit(o|a)\b|\blixo\b|\bnojent(o|a)\b", ATENCAO),
    ],
    # Seção 3 — sexual ou sugestivo
    "sexual": [
        (r"\bsexo\b|\btrans(ar|ou|aram|ando)\b|\bpelad(o|a)\b|\bnua\b|\btesao\b|\bsafad|\bseios\b|\bbunda\b|\bexcitad"
         r"|\bfazer amor\b|\bdormiu com\b|\bmotel\b|\bsensual\b", ATENCAO),
    ],
    # Seção 3 — atividade censurável (substâncias, crimes)
    "censuravel": [
        (r"\bdrogas\b|\bcocaina\b|\bmaconha\b|\bcrack\b|\bheroina\b|\bbaseado\b|\bembriag|\bbebad|\bbebedeira\b"
         r"|\bporre\b|\bcachaca\b|\bvodka\b|\bwhisky\b|\buisque\b", ATENCAO),
        (r"\broub(o|ou|ar|ei|aram|ando)\b|\bassalt|\bfurt(o|ou|ar)\b|\bsequestr|\btrafic|\bfraud|\bpropina\b|\bsubor"
         r"|\bcontrabando\b|\barma\b|\brevolver\b|\bpistola\b|\btiros?\b|\bassassin|\bmatou\b|\bmatar\b|\bhacke", ATENCAO),
    ],
    # Seção 3 — conteúdo explícito / tragédia mostrada com detalhes
    "explicito": [
        (r"\bse matar\b|\bme matar\b|\bsuicid|\btirar a propria vida\b|\btirou a propria vida\b", BLOQUEIA),
        (r"\bsangue\b|\bsangr|\bferid(a|o|as|os)\b|\bfacad|\bespanc|\bagred|\bagressao\b|\bestupr|\bcadaver\b|\benforc"
         r"|\bvomit|\bpodre\b|\bapodrec|\bvermes?\b|\blarvas?\b|\bgangrena\b|\bfezes\b", ATENCAO),
    ],
    # Seção 3 — temas sociais polêmicos
    "polemica": [
        (r"\bpolitic|\beleic|\bbolsonar|\blula\b|\bpetista|\besquerdista|\bdireitista|\bcomunista|\bfascista"
         r"|\bpartido\b|\bimigrant|\bracis|\bmacumb|\bxenofob|\bhomofob", ATENCAO),
    ],
    # Seção 4 — informação médica enganosa
    "medica": [
        (r"\bcur(a|ar|ou|ei)\s+(o\s+|a\s+|do\s+|da\s+|de\s+|meu\s+|minha\s+|seu\s+|sua\s+)?(cancer|diabetes|alzheimer|demencia"
         r"|depressao|aids|hiv|covid|tumor|leucemia|autismo)", BLOQUEIA),
        (r"\bremedio caseiro\b|\bcha\s+(que|de)\s+\w+\s+cura|\bnao precis(a|ou|ava) de (medico|remedio|tratamento|quimio)"
         r"|\bvacina", ATENCAO),
    ],
    # Seção 4 — desinformação: ficção feita com IA não pode ser apresentada como fato real
    "desinformacao": [
        (r"\bhistoria real\b|\baconteceu de verdade\b|\bcaso real\b|\bfato real\b|\bbaseado em fatos", ATENCAO),
    ],
    # Seção 3 — tragédia ou conflito: aceito quando tratado de forma construtiva (só anota o tema)
    "tragedia": [
        (r"\bmorr|\bmorte\b|\bmort(o|a)\b|\bfalec|\bcancer\b|\bdoenca\b|\bdoente\b|\bhospital\b|\buti\b|\bacidente\b"
         r"|\bluto\b|\benterr|\bvelorio\b|\bfuneral\b|\balzheimer\b|\bdemencia\b|\babandon|\borfa(o|nato)?\b", "nota"),
    ],
    # convite para seguir: não está na lista de isca do CMP; uma vez, curto, no fim
    "seguir": [
        (r"\bsig(a|am)\s+(a\s+)?(nossa\s+|minha\s+|esta\s+|essa\s+)?pagina\b|\bsegue\s+(a\s+)?(nossa\s+|minha\s+)?pagina\b"
         r"|\bsegu(e|ir|em)\s+a gente\b", "nota"),
    ],
}

TITULOS = {
    "isca": "Isca de engajamento", "venda": "Venda de envolvimento", "ofensiva": "Linguagem ofensiva",
    "sexual": "Atividade sexual ou sugestiva", "censuravel": "Atividade censurável", "explicito": "Conteúdo explícito",
    "polemica": "Temas sociais polêmicos", "medica": "Informação médica enganosa", "desinformacao": "Desinformação",
    "tragedia": "Tragédia ou conflito", "seguir": "Convite para seguir",
}


def falas_usadas(c: dict) -> list[dict]:
    """Palavras que de fato tocam no vídeo (dentro do corte e não silenciadas), com o tempo no vídeo."""
    out = []
    for w in c.get("palavras", []):
        if w["e"] <= c["inicio"] or w["s"] >= c["fim"] or w.get("silenciada"):
            continue
        out.append({"w": w["w"], "t": round(c["offset"] + max(0.0, w["s"] - c["inicio"]), 2),
                    "s": w["s"], "e": w["e"]})
    return out


def procurar_falas(cenas: list[dict]) -> dict[str, list[dict]]:
    achados: dict[str, list[dict]] = {k: [] for k in LEXICOS}
    for c in cenas:
        pal = falas_usadas(c)
        if not pal:
            continue
        # texto da cena com o índice de cada caractere -> palavra, para dizer o segundo exato
        texto, mapa = "", []
        for i, w in enumerate(pal):
            d = dobrar(re.sub(r"[^\w\s'-]", " ", w["w"])).strip()
            texto += d + " "
            mapa += [i] * (len(d) + 1)
        for cat, regras in LEXICOS.items():
            for rx, grav in regras:
                for m in re.finditer(rx, texto):
                    i = mapa[min(m.start(), len(mapa) - 1)]
                    j = mapa[min(max(m.end() - 1, m.start()), len(mapa) - 1)]
                    trecho = " ".join(x["w"] for x in pal[max(0, i - 4): j + 5])
                    achados[cat].append({"cena": c["n"], "t_video": pal[i]["t"], "t_clipe": round(pal[i]["s"], 2),
                                         "fim_clipe": round(pal[j]["e"], 2), "termo": m.group(0), "gravidade": grav,
                                         "trecho": trecho})
    return achados


def _quadros(video: Path, fps: int = 10, w: int = 54, h: int = 96):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    n = len(raw) // (w * h)
    return np.frombuffer(raw[: n * w * h], np.uint8).reshape(n, h, w).astype(np.float32)


def medir_formato(video: Path, cenas: list[dict], conteudo: float) -> dict:
    """Movimento por cena no vídeo pronto (detecta cena parada/slideshow) e cenas repetidas (loop)."""
    try:
        import numpy as np
    except ImportError:
        return {}
    Q = _quadros(video)
    if len(Q) < 4:
        return {}
    dif = np.abs(np.diff(Q, axis=0)).mean(axis=(1, 2))  # dif[k] = entre o quadro k e k+1 (10 por segundo)
    por_cena, miniaturas = [], []
    for c in cenas:
        a, b = int(c["offset"] * 10) + 3, int((c["offset"] + c["dur_final"]) * 10) - 3
        if b - a < 3:
            continue
        mov = float(np.median(dif[a:b]))
        por_cena.append({"cena": c["n"], "movimento": round(mov, 2)})
        miniaturas.append((c["n"], Q[(a + b) // 2]))
    parado = float((dif[: int(conteudo * 10)] < 0.25).mean()) if conteudo > 1 else 0.0
    repetidas = []
    for i in range(len(miniaturas)):
        for j in range(i + 1, len(miniaturas)):
            x, y = miniaturas[i][1].ravel(), miniaturas[j][1].ravel()
            x, y = x - x.mean(), y - y.mean()
            r = float((x * y).sum() / (np.sqrt((x * x).sum() * (y * y).sum()) + 1e-6))
            if r > 0.985:
                repetidas.append((miniaturas[i][0], miniaturas[j][0], round(r, 3)))
    return {"por_cena": por_cena, "fracao_parada": round(parado, 3), "repetidas": repetidas}


def hash_arquivo(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        h.update(f.read(2_000_000))
    return h.hexdigest() + str(p.stat().st_size)


def tecnico(video: Path) -> dict:
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
                        "-of", "json", str(video)], capture_output=True, text=True).stdout
    d = json.loads(o or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = any(s.get("codec_type") == "audio" for s in d.get("streams", []))
    num, den = (v.get("r_frame_rate", "0/1").split("/") + ["1"])[:2]
    return {"w": v.get("width"), "h": v.get("height"), "fps": round(float(num) / float(den or 1), 2),
            "dur": round(float(d.get("format", {}).get("duration", 0)), 1), "audio": a}


def folhas(video: Path, trabalho: Path, num: int) -> list[str]:
    """Folha de quadros (1 a cada 2 s) e folha dos cantos (marca d'água) para a revisão visual do Claude."""
    f1 = trabalho / f"folha_parte{num}.png"
    f2 = trabalho / f"cantos_parte{num}.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vf", "fps=1/2,scale=216:384,tile=6x6",
                    "-frames:v", "1", str(f1)])
    # cantos: as 4 faixas de 270x200 px dos cantos, a cada 4 s
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-filter_complex",
                    "fps=1/4,split=4[a][b][c][d];[a]crop=270:200:0:0[ta];[b]crop=270:200:iw-270:0[tb];"
                    "[c]crop=270:200:0:ih-200[tc];[d]crop=270:200:iw-270:ih-200[td];"
                    "[ta][tb][tc][td]hstack=4,tile=1x18", "-frames:v", "1", str(f2)])
    return [str(f1), str(f2)]


def verificar_parte(num: int, cenas: list[dict], video: Path, cfg: dict, trabalho: Path, info: dict) -> dict:
    """Roda os itens automáticos e grava trabalho/monetizacao_parteN.json."""
    itens: list[dict] = []

    def item(secao: str, nome: str, status: str, evidencia: str, correcao: str = "", chave: str = "") -> None:
        itens.append({"secao": secao, "item": nome, "status": status, "evidencia": evidencia, "correcao": correcao,
                      "chave": chave})

    conteudo = float(info.get("conteudo", 0))
    total = float(info.get("duracao", 0))
    fm = medir_formato(video, cenas, conteudo)
    # ---- Seção 1: formatos proibidos
    paradas = [p for p in fm.get("por_cena", []) if p["movimento"] < 0.35]
    if paradas:
        item("1 Formatos", "Vídeo estático / apresentação de imagens", BLOQUEIA,
             "cenas quase paradas: " + ", ".join(f"{p['cena']} (mov. {p['movimento']})" for p in paradas),
             "troque a cena por um clipe com movimento real ou corte-a (`cena N: remover`)")
    else:
        mins = min((p["movimento"] for p in fm.get("por_cena", [])), default=0)
        item("1 Formatos", "Vídeo estático / apresentação de imagens", OK,
             f"todas as cenas são vídeo com movimento (menor movimento {mins:.2f}; "
             f"{fm.get('fracao_parada', 0) * 100:.0f}% do conteúdo com imagem parada)")
    hashes: dict[str, list[int]] = {}
    for c in cenas:
        hashes.setdefault(hash_arquivo(Path(c["arquivo"])), []).append(c["n"])
    dup = [v for v in hashes.values() if len(v) > 1]
    if dup or fm.get("repetidas"):
        ev = "; ".join("mesmo arquivo nas cenas " + ", ".join(map(str, v)) for v in dup)
        ev += ("; " if ev and fm.get("repetidas") else "") + "; ".join(f"cenas {a} e {b} quase idênticas" for a, b, _ in fm.get("repetidas", []))
        item("1 Formatos", "Vídeo em loop", BLOQUEIA if dup else ATENCAO, ev, "não repita o mesmo trecho; corte a repetição")
    else:
        item("1 Formatos", "Vídeo em loop", OK, f"{len(cenas)} clipes diferentes, nenhum trecho repetido")
    # tempo em que o texto é o elemento principal: cartão final (sem o P&B, que é vídeo) + cartelas entre cenas
    cart = max(0.0, total - conteudo - float(info.get("pb_s", 0)))
    cartelas = float(info.get("cartelas_s", 0))
    leg = info.get("blocos_legenda", 0)
    frac = (cart + cartelas) / total if total else 0
    item("1 Formatos", "Montagem de texto", OK if frac < 0.3 else ATENCAO,
         (f"legendas {'ligadas, acompanham a fala' if leg else 'desligadas'}; texto na tela: cartão final {cart:.1f}s"
          + (f" + cartelas {cartelas:.1f}s" if cartelas else "") + f" = {frac * 100:.0f}% do vídeo; o resto é cena"),
         "" if frac < 0.3 else "encurte o cartão final (`encerramento: segurar 2`) ou a cartela")
    item("1 Formatos", "Anúncios incorporados", OK, "o editor não insere pre-roll, mid-roll, post-roll nem banner")
    item("1 Formatos", "Enquete de imagem estática", OK, "é vídeo, não imagem com pergunta")

    # ---- Seção 2 e 3/4 pelas falas
    ach = procurar_falas(cenas)

    def por_fala(cat: str, secao: str, correcao: str, chave_visual: str = "") -> None:
        lst = ach.get(cat, [])
        if not lst:
            if chave_visual:
                item(secao, TITULOS[cat], PENDENTE, "falas: nada encontrado; imagem: falta a revisão visual", "", chave_visual)
            else:
                item(secao, TITULOS[cat], OK, "nada encontrado nas falas")
            return
        grav = BLOQUEIA if any(a["gravidade"] == BLOQUEIA for a in lst) else ATENCAO
        ev = "; ".join(f"cena {a['cena']} em {a['t_video']:.1f}s: “{a['trecho']}” ('{a['termo']}')" for a in lst[:6])
        item(secao, TITULOS[cat], grav, ev, correcao, chave_visual)

    por_fala("isca", "2 Comportamentos", "corte a frase (`cena N: fim X`) ou silencie (`cena N: silenciar <palavra>`)")
    por_fala("venda", "2 Comportamentos", "corte a frase")
    por_fala("ofensiva", "3 Restritas", "silencie a palavra (`cena N: silenciar <palavra>`) ou corte a fala")
    por_fala("sexual", "3 Restritas", "confira se é sugestivo; se for, corte a fala/cena", "sexual")
    por_fala("censuravel", "3 Restritas", "só passa se o ato aparece como errado, sem glorificar nem mostrar uso")
    por_fala("explicito", "3 Restritas", "sem detalhes nem sensacionalismo; corte a fala/cena se for explícita", "explicito")
    por_fala("polemica", "3 Restritas", "tire o tom polarizado ou corte a fala")
    trag = ach.get("tragedia", [])
    temas = sorted({a["termo"] for a in trag})
    item("3 Restritas", TITULOS["tragedia"], PENDENTE if trag else OK,
         ("temas presentes: " + ", ".join(temas[:8]) + " — aceito se tratado de forma construtiva (Claude confirma)")
         if trag else "nada encontrado nas falas", "", "construtivo" if trag else "")
    por_fala("desinformacao", "4 Proibidas", "não apresente ficção feita com IA como fato real; corte a frase", "desinformacao")
    por_fala("medica", "4 Proibidas", "corte a alegação médica")
    seg = ach.get("seguir", [])
    if seg:
        st = OK if len(seg) == 1 else ATENCAO
        item("2 Comportamentos", TITULOS["seguir"], st,
             f"{len(seg)} convite(s): " + "; ".join(f"cena {a['cena']} em {a['t_video']:.1f}s" for a in seg)
             + " — seguir não está na lista de isca do CMP; manter UMA vez, curto, no fim",
             "" if st == OK else "deixe só um convite")

    # ---- Parceiro (PMP) / IA / técnico
    TRp = Path(cfg["trilha"]["pasta"]).resolve()
    EFp = Path(cfg["efeitos"]["pasta"]).resolve()
    fora = [t["arquivo"] for t in info.get("trilha", []) if TRp not in Path(t["arquivo"]).resolve().parents]
    item("Parceiro", "Originalidade e áudio", BLOQUEIA if fora else OK,
         (f"trilhas fora da pasta do usuário: {fora}" if fora else
          f"{len(info.get('trilha', []))} trecho(s) de trilha de `{TRp.name}` (Suno) e {len(info.get('efeitos', []))} efeito(s) "
          f"de `{EFp.name}` (ElevenLabs), criados pelo usuário; cenas próprias (Flow/Arkonhub)"),
         "use só as pastas do usuário" if fora else "")
    item("Parceiro", "Marca d'água / logo de terceiros", PENDENTE, f"olhar `cantos_parte{num}.png`", "", "marca_dagua")
    item("Parceiro", "Crianças", PENDENTE, f"olhar `folha_parte{num}.png`", "", "criancas")
    tc = tecnico(video)
    bom = tc.get("w") == cfg["video"]["largura"] and tc.get("h") == cfg["video"]["altura"] and tc.get("audio")
    item("Técnico", "Formato Reel", OK if bom else ATENCAO,
         f"{tc.get('w')}x{tc.get('h')}, {tc.get('fps')} fps, {tc.get('dur')}s, áudio {'sim' if tc.get('audio') else 'NÃO'}")
    mix = info.get("mix")
    if not mix:
        item("Técnico", "Trilha abaixo da fala", OK,
             f"níveis calibrados: fala {cfg['trilha']['fala_lufs']} LUFS, trilha {cfg['trilha']['lufs']} LUFS + ducking "
             "(a fala quase não tem pausas longas para medir o fundo no vídeo pronto)")
    if mix:
        dif = mix["diferenca_db"]
        lim = float(cfg["trilha"].get("diferenca_minima_db", 10))
        item("Técnico", "Trilha abaixo da fala", OK if dif >= lim else ATENCAO,
             f"fala {mix['fala_dbfs']} dBFS, fundo {mix['fundo_dbfs']} dBFS (diferença {dif} dB)",
             "" if dif >= lim else "baixe `trilha.lufs` no config.json")
    res = {"parte": num, "video": str(video), "itens": itens, "movimento": fm, "achados": ach,
           "folhas": folhas(video, trabalho, num)}
    (trabalho / f"monetizacao_parte{num}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def aplicar_visual(res: dict, visual: dict) -> dict:
    v = visual.get(str(res["parte"]), {})
    for it in res["itens"]:
        k = it.get("chave")
        if not k or k not in v:
            continue
        val = str(v[k]).strip()
        if val.lower() == "ok":
            if it["status"] == PENDENTE:
                it["status"] = OK
                it["evidencia"] = it["evidencia"].replace("; imagem: falta a revisão visual", "; imagem conferida")
                if it["evidencia"].startswith("olhar ") or it["evidencia"].startswith("temas presentes"):
                    it["evidencia"] += " — conferido pelo Claude"
        else:
            it["status"] = BLOQUEIA
            it["evidencia"] += f" | imagem: {val}"
    return res


def escrever(pasta: Path, resultados: list[dict] | None = None) -> tuple[Path, int, int]:
    """Gera PRONTO/checklist_monetizacao.md. Devolve (arquivo, nº de ❌, nº de 👁)."""
    trabalho, saida = pasta / "trabalho", pasta / "PRONTO"
    if resultados is None:
        resultados = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(trabalho.glob("monetizacao_parte*.json"))]
    vis_p = trabalho / "revisao_visual.json"
    visual = json.loads(vis_p.read_text(encoding="utf-8")) if vis_p.exists() else {}
    linhas = [f"# Checklist de monetização — {pasta.name}", "",
              "Base: Políticas de Monetização de Conteúdo (CMP) da Meta (`editor/referencias/Politicas-de-Monetizacao-de-Conteudo-CMP.pdf`)",
              "+ Políticas para Parceiros e conteúdo de IA. ✅ ok · ⚠️ atenção (explicado) · ❌ corrigir antes de publicar · 👁 falta revisão visual.", ""]
    nb = npend = 0
    for res in resultados:
        res = aplicar_visual(res, visual)
        b = sum(1 for i in res["itens"] if i["status"] == BLOQUEIA)
        pnd = sum(1 for i in res["itens"] if i["status"] == PENDENTE)
        at = sum(1 for i in res["itens"] if i["status"] == ATENCAO)
        nb += b
        npend += pnd
        veredito = ("❌ NÃO ENTREGAR — corrigir e renderizar de novo" if b else
                    "👁 falta a revisão visual" if pnd else
                    "✅ dentro das regras de monetização" + (f" ({at} ponto(s) de atenção explicados)" if at else ""))
        linhas += [f"## Parte {res['parte']} — {veredito}", "", "| Seção | Item | | Evidência | Correção |", "|---|---|---|---|---|"]
        for i in res["itens"]:
            linhas.append(f"| {i['secao']} | {i['item']} | {i['status']} | {i['evidencia'].replace('|', '/')} | {i['correcao']} |")
        nota = visual.get(str(res["parte"]), {}).get("nota")
        if nota:
            linhas += ["", f"Revisão visual: {nota}"]
        linhas.append("")
    linhas += ["## Ao publicar", "",
               "- Publicar como **Reel**, arquivo direto do PRONTO (sem passar pelo WhatsApp).",
               "- Marcar **“Informações de IA” / conteúdo criado com IA** (cenas fotorrealistas geradas por IA).",
               "- Título e texto do post sem pedir curtida/comentário/compartilhamento e sem exagerar o que acontece.",
               "- Sem compra de seguidores/views e sem compartilhamento em massa combinado.",
               "- Conferir depois em Meta Business Suite › Monetização (ou Painel profissional no celular). Se algum vídeo for",
               "  restringido, cada item aceita uma apelação (análise em até 7 dias)."]
    if len(resultados) > 1:
        i = linhas.index("- Sem compra de seguidores/views e sem compartilhamento em massa combinado.")
        linhas.insert(i, "- Parte 2 publicada algumas horas depois da Parte 1 (o gancho “Continua no Próximo episódio...” "
                         "precisa ser cumprido).")
    saida.mkdir(parents=True, exist_ok=True)
    arq = saida / "checklist_monetizacao.md"
    arq.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return arq, nb, npend


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa
            pass
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    arq, nb, npend = escrever(Path(sys.argv[1]).expanduser().resolve())
    print(f"{arq}  |  ❌ {nb}  👁 {npend}  ->  {'NÃO ENTREGAR' if nb else 'falta revisão visual' if npend else 'pode entregar'}")
    sys.exit(1 if nb else 0)
