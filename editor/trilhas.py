# -*- coding: utf-8 -*-
"""
trilhas.py — catálogo das trilhas e escolha pelo clima da história.

- catalogar(): mede cada trilha (energia, dinâmica, ritmo, brilho, graves) e, quando o Gemini responde,
  guarda uma descrição e notas de clima (suspense, tristeza, esperança...). Resultado em catalogo_trilhas.json.
- clima_das_falas(): lê as falas das cenas e dá notas de tensão, tristeza, esperança, ação e calma.
- escolher_por_clima(): cruza o clima da parte com o catálogo e devolve a trilha mais compatível e o porquê.
- sugerir_efeitos(): aponta efeitos da pasta que combinam com palavras ditas na cena (tempestade, celular...).

Uso direto:  python trilhas.py --catalogar [--gemini] [--forcar]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATALOGO = HERE / "catalogo_trilhas.json"
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".ogg", ".flac")

CLIMAS = ["tensao", "tristeza", "esperanca", "acao", "calma"]

# pasta de trilha por clima dominante
PASTA_POR_CLIMA = {
    "tensao": "Suspense",
    "tristeza": "Drama",
    "esperanca": "Piano",   # pasta nova (27/10/2026) só tem Drama, Epic, Piano e Suspense
    "acao": "Epic",
    "calma": "Piano",
}

# palavras das falas -> clima (radicais, sem acento, minúsculas)
# cada item é um radical procurado no INÍCIO de uma palavra; "palavra$" exige a palavra inteira
LEXICO = {
    "tensao": ["medo", "segred", "mentir", "menti", "polic", "sangue", "ameac", "escond", "perig", "fug", "assassin",
               "desaparec", "sumiu", "sumir", "descobr", "prova", "suspeit", "trai", "estranh", "sombra", "arma$",
               "armas$", "matou", "matar", "morto", "corpo", "grit", "socorro", "pesadel", "nunca contei", "ninguem sabe",
               "nao conta", "cuidado", "vigi", "persegu", "delegac", "cadeia", "preso", "presa", "sequestr", "roub",
               "golpe", "chantag", "vingan", "espi"],
    "tristeza": ["morreu", "morte", "enterr", "velor", "perdoa", "perdao", "perdi", "perdeu", "chor", "lagrim", "saudade",
                 "sozinh", "abandon", "nunca mais", "doen", "hospital", "cancer", "despedid", "adeus", "triste", "dor$",
                 "dores$", "sofr", "vazio", "culpa", "arrepend", "tarde demais", "faleceu", "partiu", "ultimo", "carta",
                 "lembr", "orfa", "viuv", "coracao partido", "magoa", "ferid", "luto$", "sem se falar", "nao consegui"],
    "esperanca": ["recome", "sonho", "conquist", "orgulho", "super", "acredit", "esperanc", "futuro", "feliz",
                  "sorri", "abrac", "juntos", "amor", "amo$", "amav", "gratid", "obrigad", "milagre", "vida nova",
                  "forca", "coragem", "familia", "reencontr", "perdoo", "te amo", "luz", "renasc", "chance", "diferente"],
    "acao": ["luta$", "lutar", "lutou", "guerra", "correu", "correr", "corram", "atac", "explod", "batalh", "tiro", "bomba",
             "quebr", "invad", "pulou", "pular", "salt", "persegu", "fuga", "rapid", "depressa", "enfrent", "derrot",
             "venceu", "vencer", "brig", "soco", "chuta", "disparo", "sirene"],
    "calma": ["cafe", "manha", "convers", "trabalh", "rotina", "vizinh", "jardim", "almoc", "jantar", "domingo",
              "passeio", "praca", "escola", "loja", "mercado", "brincad", "risad", "piada", "tranquil", "calm",
              "sossego", "descans", "ferias", "praia", "sol$", "cafezinho", "bom dia"],
}

# palavras das falas -> pasta de efeito sonoro
EFEITOS_POR_PALAVRA = [
    (["tempestade", "chuva", "trovao", "trovoada", "raio$", "raios$", "temporal", "chovendo"], "Tempestade"),
    (["mar$", "praia", "onda", "oceano", "maresia"], "Mar"),
    (["cachorro", "latid", "rosn", "cao$", "caes$", "latindo"], "Cachoro com raiva"),
    (["lobo", "uivo", "uiv"], "Uivo de Lobo"),
    (["telefone", "celular", "ligou", "ligacao", "ligar", "mensagem", "whatsapp", "toca o telefone", "tocou o telefone"], "Celular Vibrando"),
    (["hospital", "monitor", "uti$", "coma$", "enfermar", "soro$", "cirurg"], "Monitor Cardiaco"),
    (["coracao batendo", "coracao dispar", "coracao acelera", "batendo forte", "bater forte", "palpit"], "batida de Coração"),
    (["relogio", "tic-tac", "tic tac", "contando os segundos", "contando as horas"], "Relogio"),
    (["passarinho", "passaros", "passaro", "parque", "amanhec"], "Passáros"),
    (["rio$", "riacho", "corrego", "cachoeira", "correnteza"], "Rio Corrego"),
    (["fogo", "incendio", "queimad", "fumaca", "chamas", "queim"], "Queimada"),
    (["vento", "ventania", "deserto"], "ventania"),
    (["multidao", "lotad", "imprensa", "jornalista", "plateia", "entrevista coletiva"], "Sala Lotada"),
    (["computador", "digit", "teclado", "notebook"], "teclado computador"),
    (["mouse", "clique", "clica"], "Click Mouse"),
    (["foto$", "fotos$", "camera", "fotograf", "flash"], "Flash camera"),
]

# palavras no NOME do arquivo -> notas de clima (fallback quando não há descrição do Gemini)
NOME_PARA_CLIMA = [
    (["pulse", "glass", "hollow", "shadow pulse", "black"], {"tensao": 5, "energia": 3}),
    (["storm", "descent", "shadow's"], {"acao": 4, "tensao": 4, "energia": 4}),
    (["elegy", "silent", "silêncio", "silencio", "ecos"], {"tristeza": 5, "energia": 2}),
    (["ivory", "drift", "seaside", "echoes", "piano"], {"tristeza": 3, "calma": 3, "energia": 2}),
    (["brighter", "days", "horizons", "hope", "light"], {"esperanca": 5, "energia": 3}),
    (["soft", "morning"], {"calma": 5, "energia": 2}),
]


# ----------------------------------------------------------------------------- util
def dobrar(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def chave_gemini() -> str | None:
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return k
    for env in [HERE / ".env", Path.home() / ".config" / "watch" / ".env"]:
        if env.exists():
            for linha in env.read_text(encoding="utf-8", errors="replace").splitlines():
                if linha.strip().startswith("GEMINI_API_KEY="):
                    v = linha.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    return None


def listar(pasta: Path) -> list[Path]:
    return sorted([p for p in pasta.rglob("*") if p.suffix.lower() in AUDIO_EXT])


# ----------------------------------------------------------------------------- medidas
def medir(path: Path) -> dict:
    """Medidas objetivas da trilha, com ffmpeg + numpy."""
    import numpy as np
    sr = 22050
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32)
    dur = len(a) / sr
    if dur < 2:
        return {"duracao": round(dur, 1)}
    hop = int(sr * 0.05)
    n = len(a) // hop
    frames = a[: n * hop].reshape(n, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1)) + 1e-9
    db = 20 * np.log10(rms)
    ativo = db > (db.max() - 40)
    db_a = db[ativo] if ativo.any() else db
    # onsets: subidas rápidas do envelope
    flux = np.diff(db)
    limiar = max(2.0, np.percentile(flux, 90))
    onsets = (flux > limiar) & (np.r_[True, flux[:-1] <= flux[1:]][: len(flux)])
    taxa_onsets = float(onsets.sum() / max(1e-6, (len(flux) * 0.05)))
    # espectro: brilho e graves (STFT simples)
    win = 2048
    nfr = (len(a) - win) // win
    idx = np.arange(0, nfr * win, win)[:400] if nfr > 400 else np.arange(0, max(1, nfr) * win, win)
    freqs = np.fft.rfftfreq(win, 1 / sr)
    cents, lows = [], []
    janela = np.hanning(win)
    for i in idx:
        seg = a[i: i + win]
        if len(seg) < win:
            break
        esp = np.abs(np.fft.rfft(seg * janela)) ** 2
        tot = esp.sum() + 1e-12
        cents.append(float((esp * freqs).sum() / tot))
        lows.append(float(esp[freqs < 150].sum() / tot))
    return {
        "duracao": round(dur, 1),
        "nivel_db": round(float(np.median(db_a)), 1),          # nível típico (dBFS)
        "dinamica_db": round(float(np.percentile(db_a, 95) - np.percentile(db_a, 10)), 1),
        "onsets_por_s": round(taxa_onsets, 2),                  # ritmo / pulsação
        "brilho_hz": round(float(np.median(cents)) if cents else 0.0),
        "graves": round(float(np.median(lows)) if lows else 0.0, 3),
    }


def notas_pelo_nome(nome: str) -> dict:
    n = dobrar(nome)
    notas: dict = {}
    for chaves, vals in NOME_PARA_CLIMA:
        if any(k in n for k in chaves):
            for k, v in vals.items():
                notas[k] = max(notas.get(k, 0), v)
    return notas


def notas_pela_pasta(pasta: str) -> dict:
    p = dobrar(pasta)
    if "suspense" in p:
        return {"tensao": 4}
    if "drama" in p:
        return {"tristeza": 4}
    if "epic" in p:
        return {"acao": 4, "tensao": 2}
    if "inspir" in p:
        return {"esperanca": 4}
    if "piano" in p:
        return {"tristeza": 3, "calma": 2}
    return {"calma": 4}


# ----------------------------------------------------------------------------- Gemini
PROMPT_GEMINI = (
    "Você é um diretor musical de vídeos de histórias curtas (drama familiar, suspense, superação). "
    "Ouça esta trilha e responda SOMENTE em JSON com as chaves: "
    "clima (lista de 2 a 4 palavras em português entre: suspense, tensão, drama, tristeza, melancolia, esperança, "
    "inspiração, ação, épico, calma, leve, romântico, nostalgia), energia (1 a 5), tensao (1 a 5), tristeza (1 a 5), "
    "esperanca (1 a 5), acao (1 a 5), calma (1 a 5), ritmo (lento, médio ou rápido), instrumentos (lista curta), "
    "descricao (uma frase), cenas_ideais (uma frase sobre que tipo de cena combina)."
)


def descrever_gemini(path: Path, key: str, modelos: list[str] | None = None, inicio: float = 20.0, dur: float = 40.0) -> dict | None:
    modelos = modelos or ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-2.5-flash", "gemini-flash-latest"]
    audio = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(inicio), "-t", str(dur), "-i", str(path), "-vn", "-ac", "1",
                            "-ar", "22050", "-b:a", "48k", "-f", "mp3", "-"], capture_output=True, check=True).stdout
    if len(audio) < 1000:
        audio = subprocess.run(["ffmpeg", "-v", "error", "-t", str(dur), "-i", str(path), "-vn", "-ac", "1",
                                "-ar", "22050", "-b:a", "48k", "-f", "mp3", "-"], capture_output=True, check=True).stdout
    body = {"contents": [{"parts": [{"inline_data": {"mime_type": "audio/mpeg", "data": base64.b64encode(audio).decode()}},
                                    {"text": PROMPT_GEMINI}]}],
            "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2}}
    dados = json.dumps(body).encode()
    for modelo in modelos:
        for tentativa in range(4):
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                                         data=dados, headers={"x-goog-api-key": key, "Content-Type": "application/json"})
            try:
                r = json.load(urllib.request.urlopen(req, timeout=120))
                txt = r["candidates"][0]["content"]["parts"][0]["text"]
                d = json.loads(txt)
                if isinstance(d, list):
                    d = d[0]
                d["modelo"] = modelo
                return d
            except urllib.error.HTTPError as e:
                if e.code == 429:          # cota por minuto: espera e tenta o mesmo modelo
                    time.sleep(20 * (tentativa + 1))
                    continue
                if e.code in (503, 500):   # sobrecarga: próximo modelo
                    break
                return None
            except Exception:
                break
    return None


# ----------------------------------------------------------------------------- catálogo
def carregar_catalogo() -> dict:
    if CATALOGO.exists():
        try:
            return json.loads(CATALOGO.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"trilhas": {}}


def salvar_catalogo(cat: dict) -> None:
    tmp = CATALOGO.with_suffix(".tmp")
    tmp.write_text(json.dumps(cat, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, CATALOGO)   # troca atômica: quem lê nunca vê o arquivo pela metade


def catalogar(pasta: Path, usar_gemini: bool = False, forcar: bool = False, log=print, gemini_so_novos: bool = False) -> dict:
    """Mede trilhas novas/alteradas. Com usar_gemini, pede descrição das que não têm (ou só das novas, se gemini_so_novos)."""
    cat = carregar_catalogo()
    trilhas = cat.setdefault("trilhas", {})
    arquivos = listar(pasta)
    key = chave_gemini() if usar_gemini else None
    vivos = set()
    mudou = False
    for p in arquivos:
        k = str(p)
        vivos.add(k)
        st = p.stat()
        ent = trilhas.get(k)
        novo = ent is None or forcar or ent.get("tamanho") != st.st_size
        if novo:
            log(f"  medindo  {p.parent.name} / {p.name}")
            ent = {"pasta": p.parent.name, "nome": p.stem, "tamanho": st.st_size}
            ent.update(medir(p))
            trilhas[k] = ent
            mudou = True
        if key and (novo or (not ent.get("gemini") and not gemini_so_novos)):
            log(f"  Gemini ouvindo  {p.name}")
            d = descrever_gemini(p, key)
            if d:
                ent["gemini"] = d
                mudou = True
                time.sleep(7.0)   # respeita a cota por minuto
            else:
                log("     (Gemini não respondeu; fica só com as medidas)")
        if mudou:
            salvar_catalogo(cat)
    if not mudou and set(trilhas) == vivos:
        return cat
    for k in list(trilhas):
        if k not in vivos:
            del trilhas[k]
    # normalização de energia dentro do catálogo (0..1)
    niveis = [t.get("nivel_db") for t in trilhas.values() if t.get("nivel_db") is not None]
    ons = [t.get("onsets_por_s") for t in trilhas.values() if t.get("onsets_por_s") is not None]
    if niveis and ons:
        lo, hi = min(niveis), max(niveis)
        olo, ohi = min(ons), max(ons)
        for t in trilhas.values():
            if t.get("nivel_db") is None:
                continue
            e1 = (t["nivel_db"] - lo) / (hi - lo) if hi > lo else 0.5
            e2 = (t["onsets_por_s"] - olo) / (ohi - olo) if ohi > olo else 0.5
            t["energia_medida"] = round(0.6 * e1 + 0.4 * e2, 2)
    salvar_catalogo(cat)
    return cat


def notas_da_trilha(ent: dict) -> dict:
    """Notas 0..5 por clima + energia 0..1, vindas do Gemini quando há, senão do nome/pasta."""
    g = ent.get("gemini") or {}
    notas = {c: 0.0 for c in CLIMAS}
    if g:
        for c in CLIMAS:
            try:
                notas[c] = float(g.get(c, 0) or 0)
            except (TypeError, ValueError):
                pass
        clima = [dobrar(str(x)) for x in (g.get("clima") or [])]
        for x in clima:
            if "suspense" in x or "tens" in x:
                notas["tensao"] = max(notas["tensao"], 4)
            if "trist" in x or "melanc" in x or "drama" in x or "nostalg" in x:
                notas["tristeza"] = max(notas["tristeza"], 4)
            if "esperan" in x or "inspir" in x or "roman" in x:
                notas["esperanca"] = max(notas["esperanca"], 4)
            if "acao" in x or "epic" in x:
                notas["acao"] = max(notas["acao"], 4)
            if "calma" in x or "leve" in x:
                notas["calma"] = max(notas["calma"], 4)
        try:
            energia = (float(g.get("energia", 3)) - 1) / 4
        except (TypeError, ValueError):
            energia = ent.get("energia_medida", 0.5)
    else:
        base = notas_pela_pasta(ent.get("pasta", ""))
        base.update({k: v for k, v in notas_pelo_nome(ent.get("nome", "")).items() if k != "energia"})
        for c in CLIMAS:
            notas[c] = float(base.get(c, 0))
        energia = ent.get("energia_medida", 0.5)
    return {"notas": notas, "energia": float(energia)}


# ----------------------------------------------------------------------------- clima das falas
def _padrao(radical: str) -> str:
    """radical no início de palavra; 'x$' = palavra inteira."""
    if radical.endswith("$"):
        return r"\b" + re.escape(radical[:-1]) + r"\b"
    return r"\b" + re.escape(radical)


def clima_das_falas(textos: list[str]) -> dict:
    """Notas 0..5 por clima a partir das falas (lista de textos, uma por cena) e intensidade 0..1."""
    txt = dobrar(" ".join(textos))
    palavras = max(1, len(txt.split()))
    bruto = {c: 0 for c in CLIMAS}
    achados: dict = {c: [] for c in CLIMAS}
    for c, radicais in LEXICO.items():
        for r in radicais:
            n = len(re.findall(_padrao(r), txt))
            if n:
                bruto[c] += n
                achados[c].append(r.rstrip("$"))
    # por 100 palavras, em escala 0..5
    notas = {c: min(5.0, round(bruto[c] / palavras * 100 * 1.2, 2)) for c in CLIMAS}
    excl = txt.count("!") + txt.count("?")
    intensidade = min(1.0, 0.25 + 0.5 * (notas["tensao"] + notas["acao"]) / 10 + 0.15 * min(1, excl / 6))
    dominante = max(CLIMAS, key=lambda c: notas[c]) if any(notas.values()) else "tristeza"
    return {"notas": notas, "intensidade": round(intensidade, 2), "dominante": dominante,
            "palavras": palavras, "achados": {c: sorted(set(v))[:8] for c, v in achados.items()}}


def clima_por_cena(textos: list[str]) -> list[dict]:
    return [clima_das_falas([t]) for t in textos]


# ----------------------------------------------------------------------------- escolha
def escolher_por_clima(cat: dict, clima: dict, necessario: float, estilo_usuario: str | None = None,
                       pasta_forcada: str | None = None, excluir: set | None = None) -> tuple[Path | None, str]:
    trilhas = cat.get("trilhas", {})
    if not trilhas:
        return None, "catálogo vazio"
    notas = clima["notas"]
    inten = clima["intensidade"]
    total = sum(notas.values()) or 1.0
    peso = {c: notas[c] / total for c in CLIMAS}
    # pasta preferida: o estilo do usuário manda; senão, o clima dominante
    pasta_pref = pasta_forcada
    if not pasta_pref and estilo_usuario:
        e = dobrar(estilo_usuario)
        for chave, pasta in [("suspense", "Suspense"), ("terror", "Suspense"), ("tens", "Suspense"), ("drama", "Drama"),
                             ("trist", "Drama"), ("melanc", "Piano"), ("piano", "Piano"), ("acao", "Epic"), ("epic", "Epic"),
                             ("inspir", "Piano"), ("emocion", "Piano"), ("esperan", "Piano"),
                             ("normal", "Piano"), ("violao", "Piano"), ("calm", "Piano"), ("leve", "Piano")]:
            if chave in e:
                pasta_pref = pasta
                break
    if not pasta_pref:
        dom = clima["dominante"]
        pasta_pref = PASTA_POR_CLIMA[dom]
        # tristeza com pouca intensidade e pouca tensão -> piano
        if dom == "tristeza" and inten < 0.4 and notas["tensao"] < 1.0:
            pasta_pref = "Piano"
    # estilo pedido (briefing ou --estilo) é filtro, não só preferência
    candidatas = {k: e for k, e in trilhas.items() if dobrar(e.get("pasta", "")) == dobrar(pasta_pref)} \
        if (pasta_forcada or estilo_usuario) else trilhas
    if not candidatas:
        candidatas = trilhas
    melhor, melhor_s, linhas = None, -1e9, []
    for k, ent in candidatas.items():
        if excluir and k in excluir:
            continue
        nt = notas_da_trilha(ent)
        afin = sum(peso[c] * nt["notas"][c] for c in CLIMAS) / 5.0          # 0..1
        energia_alvo = inten
        enc = 1.0 - abs(nt["energia"] - energia_alvo)                       # 0..1
        s = 0.55 * afin + 0.25 * enc
        if dobrar(ent.get("pasta", "")) == dobrar(pasta_pref):
            s += 0.25
        dur = ent.get("duracao", 0)
        if dur >= necessario:
            s += 0.08
        elif dur < 70:
            s -= 0.05
        if ent.get("gemini"):
            s += 0.03
        linhas.append((s, k, afin, enc))
        if s > melhor_s:
            melhor, melhor_s = k, s
    if melhor is None:
        return None, "nenhuma trilha"
    ent = trilhas[melhor]
    g = ent.get("gemini") or {}
    por_que = (f"clima das falas: " + ", ".join(f"{c} {notas[c]:.1f}" for c in CLIMAS if notas[c] > 0)
               + f"; intensidade {inten:.2f}; pasta preferida: {pasta_pref}")
    desc = g.get("descricao") or "sem descrição do Gemini (escolha pelas medidas e pelo nome)"
    por_que += f" -> {ent['pasta']} / {ent['nome']} ({ent.get('duracao', 0):.0f}s): {desc}"
    return Path(melhor), por_que


def ranking(cat: dict, clima: dict, necessario: float, n: int = 5) -> list[tuple[float, str]]:
    """Top n para mostrar no plano."""
    out = []
    excl: set = set()
    for _ in range(n):
        p, _ = escolher_por_clima(cat, clima, necessario, excluir=excl)
        if p is None:
            break
        excl.add(str(p))
        out.append(str(p))
    return out


# ----------------------------------------------------------------------------- efeitos sugeridos
def sugerir_efeitos(textos: list[str], pasta_efeitos: Path) -> list[dict]:
    existentes = {dobrar(d.name): d.name for d in pasta_efeitos.iterdir() if d.is_dir()} if pasta_efeitos.exists() else {}
    sug = []
    for i, t in enumerate(textos, 1):
        d = " " + dobrar(t) + " "
        for palavras, pasta in EFEITOS_POR_PALAVRA:
            for w in palavras:
                if re.search(_padrao(w), d):
                    nome = existentes.get(dobrar(pasta), pasta)
                    sug.append({"cena": i, "efeito": nome, "palavra": w.rstrip("$")})
                    break
    return sug


# ----------------------------------------------------------------------------- CLI
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalogar", action="store_true")
    ap.add_argument("--gemini", action="store_true", help="pede ao Gemini uma descrição de cada trilha")
    ap.add_argument("--forcar", action="store_true")
    ap.add_argument("--pasta", default=None)
    a = ap.parse_args()
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    pasta = Path(a.pasta or cfg["trilha"]["pasta"])
    if a.catalogar:
        cat = catalogar(pasta, usar_gemini=a.gemini, forcar=a.forcar)
        print(f"\n{len(cat['trilhas'])} trilhas no catálogo: {CATALOGO}")
        for k, t in cat["trilhas"].items():
            g = t.get("gemini") or {}
            print(f"- {t['pasta']:28s} {t['nome'][:40]:40s} {t.get('duracao', 0):5.0f}s energia {t.get('energia_medida', 0):.2f} "
                  f"{'| ' + ', '.join(g.get('clima', [])) if g else ''}")
    else:
        ap.print_help()


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa
            pass
    main()
