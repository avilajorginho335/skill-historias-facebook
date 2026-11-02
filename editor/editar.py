#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""
editar.py — Editor automático das histórias do Facebook (Parte 1 / Parte 2).

Entrada : uma pasta com as cenas numeradas (01.mp4, 02.mp4 ... ou "cena 1.mp4"),
          opcionalmente um briefing.txt dentro dela (veja briefing_exemplo.txt).
Saída   : <pasta>/PRONTO/Parte 1.mp4, Parte 2.mp4 e relatorio.md
          <pasta>/trabalho/  (cache: transcrições, legendas .ass, quadros, filtros)

Uso:
  python editar.py "<pasta da história>" [--briefing arquivo] [--estilo drama]
                   [--parte 1|2] [--so-planejar] [--forcar-transcricao] [--saida PASTA]

Precisa de: ffmpeg/ffprobe no PATH. Transcrição: Groq (chave GROQ_API_KEY ou
~/.config/watch/.env) ou, sem chave, faster-whisper local.
"""
from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import random
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import trilhas  # noqa: E402  (catálogo e escolha da trilha pelo clima)
import camera  # noqa: E402  (zoom, enquadramento 9:16 e cor medidos nos exemplos)
import monetizacao  # noqa: E402  (checklist das Políticas de Monetização de Conteúdo)

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}


# ----------------------------------------------------------------------------- util
def log(msg: str = "") -> None:
    print(msg, flush=True)


def erro(msg: str) -> None:
    log("ERRO: " + msg)
    sys.exit(1)


def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True)
    if p.returncode != 0:
        log(p.stderr.decode("utf-8", "replace")[-6000:])
        raise RuntimeError("comando falhou: " + " ".join(cmd[:3]) + " ...")
    return p


def dobrar(s: str) -> str:
    """minúsculas sem acento, para comparar nomes."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower().strip()


def numero_natural(p: Path) -> tuple:
    m = re.search(r"\d+", p.stem)
    return (int(m.group()) if m else 10**9, p.stem.lower())


def fmt(t: float) -> str:
    return f"{t:.3f}"


def carregar_cfg() -> dict:
    with open(HERE / "config.json", encoding="utf-8") as f:
        return json.load(f)


# ----------------------------------------------------------------------------- ffprobe / medições
def ffprobe(path: Path) -> dict:
    p = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                       capture_output=True)
    try:
        return json.loads(p.stdout.decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError:
        return {}


def probe(path: Path) -> dict:
    j = ffprobe(path)
    dur = float(j.get("format", {}).get("duration", 0) or 0)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), None)
    fps = 30.0
    if v and v.get("r_frame_rate") and "/" in v["r_frame_rate"]:
        n, d = v["r_frame_rate"].split("/")
        fps = float(n) / float(d or 1)
    return {"dur": dur, "w": int(v["width"]) if v else 0, "h": int(v["height"]) if v else 0, "fps": fps, "audio": a is not None}


def medir_lufs(path: Path, inicio: float | None = None, dur: float | None = None) -> float | None:
    cmd = ["ffmpeg", "-v", "info", "-nostats"]
    if inicio is not None:
        cmd += ["-ss", fmt(inicio)]
    cmd += ["-i", str(path)]
    if dur is not None:
        cmd += ["-t", fmt(dur)]
    cmd += ["-vn", "-af", "ebur128=framelog=quiet", "-f", "null", "-"]
    p = subprocess.run(cmd, capture_output=True)
    m = re.findall(r"I:\s+(-?[\d.]+)\s+LUFS", p.stderr.decode("utf-8", "replace"))
    return float(m[-1]) if m else None


def medir_movimento(path: Path, t0: float, t1: float) -> float | None:
    """Diferença média entre quadros (0-255) em um trecho; ~0 = imagem parada, 2-5 = pessoa falando, 8+ = ação/câmera."""
    if t1 - t0 < 0.3:
        return None
    try:
        import numpy as np  # noqa
    except ImportError:
        return None
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", fmt(t0), "-t", fmt(t1 - t0), "-i", str(path),
                          "-vf", "fps=10,scale=54:96", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True).stdout
    n = len(raw) // (54 * 96)
    if n < 2:
        return None
    f = np.frombuffer(raw[: n * 54 * 96], np.uint8).reshape(n, 96 * 54).astype(np.float32)
    return float(np.abs(np.diff(f, axis=0)).mean())


def verificar_mix(path: Path, cenas: list[dict], fim_conteudo: float) -> dict | None:
    """Mede, no vídeo pronto, o nível da fala e o do fundo (trilha) nos silêncios entre falas."""
    try:
        import numpy as np  # noqa
    except ImportError:
        return None
    sr = 16000
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.float32)
    win = sr // 10
    n = len(a) // win
    if n < 10:
        return None
    db = 20 * np.log10(np.sqrt((a[: n * win].reshape(n, win) ** 2).mean(axis=1)) + 1e-9)
    fala = np.zeros(n, bool)
    for c in cenas:
        for w in c["palavras"]:
            s = c["offset"] + max(0.0, w["s"] - c["inicio"])
            e = c["offset"] + max(0.0, w["e"] - c["inicio"])
            fala[int(s * 10): int(e * 10) + 1] = True
    # fundo: janelas sem fala, longe (>0,6 s) de qualquer palavra e dentro do conteúdo (antes do encerramento)
    perto = fala.copy()
    for k in range(1, 7):
        perto[k:] |= fala[:-k]
        perto[:-k] |= fala[k:]
    fundo = (~perto) & (np.arange(n) < int(fim_conteudo * 10) - 10) & (np.arange(n) > 25)
    for c in cenas:  # cena sem fala (ex.: entrada na igreja): a trilha é o som da cena, não "fundo" de fala
        if not c["palavras"] and c.get("offset") is not None:
            fundo[int(c["offset"] * 10): int((c["offset"] + c["dur_final"]) * 10) + 1] = False
    for c in cenas:  # na cartela só toca o efeito de suspense (de propósito): não é "trilha no fundo"
        if c.get("cartela_ini") is not None and c.get("cartela_depois"):
            a = int(c["cartela_ini"] * 10) - 5
            fundo[max(0, a): a + int(float(c["cartela_depois"]["duracao"]) * 10) + 10] = False
    if fala.sum() < 10 or fundo.sum() < 10:
        return None
    nf, nb = float(np.median(db[fala])), float(np.median(db[fundo]))
    return {"fala_dbfs": round(nf, 1), "fundo_dbfs": round(nb, 1), "diferenca_db": round(nf - nb, 1)}


def medir_pico_db(path: Path, dur: float | None = None) -> float | None:
    """Pico do arquivo; com dur, só do trecho que vai tocar (efeito cortado no tamanho da cartela, por exemplo)."""
    p = subprocess.run(["ffmpeg", "-v", "info", "-nostats"] + (["-t", fmt(dur)] if dur else []) + ["-i", str(path), "-vn",
                        "-af", "astats=measure_perchannel=none:measure_overall=Peak_level", "-f", "null", "-"],
                       capture_output=True)
    m = re.findall(r"Peak level dB:\s+(-?[\d.]+)", p.stderr.decode("utf-8", "replace"))
    return float(m[-1]) if m else None


def medir_tempo_pico(path: Path) -> float:
    """Instante (s) de maior energia do efeito, para alinhar o pico do som com o ponto da transição."""
    try:
        import numpy as np  # noqa
    except ImportError:
        return 0.0
    sr = 8000
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.float32)
    w = sr // 50
    n = len(a) // w
    if n < 1:
        return 0.0
    return float(np.argmax((a[: n * w].reshape(n, w) ** 2).mean(axis=1)) * w / sr)


def regra_do_som(cfg: dict, arq: Path) -> dict:
    """Volume e momento de um efeito pedido, pela pasta dele (config.json > efeitos.niveis)."""
    N = cfg["efeitos"].get("niveis", {})
    return dict(N.get(dobrar(arq.parent.name)) or N.get("padrao") or {"pico_db": -8, "pico_em": 0.0})


def lista_de_sons(texto: str) -> list[str]:
    """'Flash Camera 01 + Woosh 02' / 'Flash Camera 01 e Woosh 02' -> os dois nomes."""
    return [x.strip() for x in re.split(r"\s*(?:\+|,|\s\be\b\s)\s*", texto) if x.strip()]


def quando_tocar(regra: dict, arq: Path, ponto: float, estado: dict) -> float:
    """Início do efeito: com 'pico_em', o pico do som cai em ponto + pico_em; senão começa 'antecipar' antes."""
    if "pico_em" in regra:
        k = f"tpico:{arq}"
        if k not in estado:
            estado[k] = medir_tempo_pico(arq)
        return max(0.0, ponto + float(regra["pico_em"]) - float(estado[k]))
    return max(0.0, ponto - float(regra.get("antecipar", 0.25)))


# ----------------------------------------------------------------------------- transcrição
def chave_groq() -> str | None:
    k = os.environ.get("GROQ_API_KEY")
    if k:
        return k
    for env in [HERE / ".env", Path.home() / ".config" / "watch" / ".env"]:
        if env.exists():
            for linha in env.read_text(encoding="utf-8", errors="replace").splitlines():
                if linha.strip().startswith("GROQ_API_KEY="):
                    v = linha.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    return None


def transcrever_groq(path: Path, key: str) -> list[dict]:
    audio = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                            "-b:a", "64k", "-f", "mp3", "-"], capture_output=True, check=True).stdout
    b = uuid.uuid4().hex

    def campo(n: str, v: str) -> bytes:
        return f"--{b}\r\nContent-Disposition: form-data; name=\"{n}\"\r\n\r\n{v}\r\n".encode()

    body = (campo("model", "whisper-large-v3") + campo("language", "pt") + campo("response_format", "verbose_json")
            + campo("timestamp_granularities[]", "word") + campo("timestamp_granularities[]", "segment"))
    body += (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"audio.mp3\"\r\n"
             f"Content-Type: audio/mpeg\r\n\r\n").encode() + audio + b"\r\n" + f"--{b}--\r\n".encode()
    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/audio/transcriptions", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={b}",
                 "User-Agent": "curl/8.0", "Accept": "application/json"})
    r = None
    for tentativa in range(3):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=180))
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and tentativa < 2:
                time.sleep(6 * (tentativa + 1))
                continue
            raise
    return [{"w": w["word"].strip(), "s": float(w["start"]), "e": float(w["end"])}
            for w in (r or {}).get("words", []) if str(w.get("word", "")).strip()]


_modelo_local = None


def transcrever_local(path: Path, modelo: str = "small") -> list[dict]:
    global _modelo_local
    import numpy as np  # noqa
    from faster_whisper import WhisperModel  # noqa
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    audio = np.frombuffer(raw, dtype=np.float32)
    if _modelo_local is None:
        try:
            m = WhisperModel(modelo, device="cuda", compute_type="float16")
            list(m.transcribe(audio[:16000], language="pt")[0])
            _modelo_local = m
            log("   (faster-whisper na GPU)")
        except Exception:
            _modelo_local = WhisperModel(modelo, device="cpu", compute_type="int8")
            log("   (faster-whisper na CPU — mais lento)")
    segs, _ = _modelo_local.transcribe(audio, language="pt", word_timestamps=True, vad_filter=True, beam_size=5)
    palavras = []
    for s in segs:
        for w in (s.words or []):
            if w.word.strip():
                palavras.append({"w": w.word.strip(), "s": float(w.start), "e": float(w.end)})
    return palavras


def transcrever(path: Path, trabalho: Path, forcar: bool, modelo_local: str) -> list[dict]:
    cache_dir = trabalho / "transcricoes"
    cache_dir.mkdir(parents=True, exist_ok=True)
    st = path.stat()
    cache = cache_dir / f"{path.stem}_{st.st_size}_{int(st.st_mtime)}.json"
    if cache.exists() and not forcar:
        return json.loads(cache.read_text(encoding="utf-8"))
    key = chave_groq()
    palavras: list[dict] | None = None
    if key:
        try:
            palavras = transcrever_groq(path, key)
        except Exception as e:  # noqa
            log(f"   Groq falhou ({str(e)[:120]}); usando faster-whisper local")
    if palavras is None:
        palavras = transcrever_local(path, modelo_local)
    cache.write_text(json.dumps(palavras, ensure_ascii=False, indent=1), encoding="utf-8")
    return palavras


# ----------------------------------------------------------------------------- briefing
# cores por nome para cartelas e texto final ("letra amarela", "branca", "#FCD100")
CORES = {"amarel": "EDFC00", "dourad": "FCD100", "branc": "FFFFFF", "vermelh": "E53935", "laranj": "FF9800",
         "azul": "4FC3F7", "verde": "66BB6A", "cinza": "BDBDBD", "rosa": "F48FB1", "roxo": "B388FF", "lilas": "B388FF"}


def cor_do_texto(dp: str) -> str | None:
    """'letra amarela' / 'cor branca' / 'amarelo' / '#FCD100' -> RRGGBB (texto já sem acento, minúsculo)."""
    t = re.sub(r"^(letra|letras|cor|texto|na cor)\s+", "", dp.strip())
    m = re.fullmatch(r"#?([0-9a-f]{6})", t)
    if m:
        return m.group(1).upper()
    for k, v in CORES.items():
        if re.fullmatch(k + r"\w*", t):
            return v
    return None


def estilo_do_texto(dp: str) -> str | None:
    """'fade in' / 'fade out' / 'fade' / 'digitando' / 'letra por letra' -> estilo da cartela ou do texto final."""
    t = re.sub(r"^(estilo|no estilo|efeito de texto)\s+", "", dp.strip())
    if re.fullmatch(r"fade\s*in\s*(e|/|-)\s*(fade\s*)?out|fade", t):
        return "fade"
    if re.fullmatch(r"fade\s*in", t):
        return "fade in"
    if re.fullmatch(r"fade\s*out", t):
        return "fade out"
    if re.fullmatch(r"digit\w*|maquina de escrever|datilograf\w*", t):
        return "digitando"
    if re.fullmatch(r"(letra por letra|revelar|revelando|degrade|gradiente)", t):
        return "revelar"
    return None


def parse_briefing(texto: str) -> dict:
    b: dict = {"cenas": {}}
    for bruta in texto.splitlines():
        # comentário: linha que começa com "#" ou " # texto" no fim; "#1" dentro de nome de arquivo (efeito Suspense/#1) fica
        if bruta.lstrip().startswith("#"):
            continue
        linha = re.split(r"\s#(?=\s|$)", bruta, maxsplit=1)[0].strip()
        if not linha:
            continue
        d = dobrar(linha)
        m = re.match(r"estilo\s*[:=]\s*(.+)", d)
        if m:
            b["estilo"] = m.group(1).strip()
            continue
        m = re.match(r"trilha\s*(?:da\s*)?parte\s*([12])\s*[:=]\s*(.+)", d)
        if m:
            b[f"trilha_parte{m.group(1)}"] = linha.split(":", 1)[-1].strip() if ":" in linha else m.group(2)
            continue
        m = re.match(r"trilha\s*[:=]\s*(.+)", d)
        if m:
            b["trilha"] = linha.split(":", 1)[-1].strip() if ":" in linha else m.group(1)
            continue
        m = re.match(r"parte\s*1\s*(?:ate|até)\s*(?:a\s*)?cena\s*[:=]?\s*(\d+)", d)
        if m:
            b["parte1_cena"] = int(m.group(1))
            continue
        m = re.match(r"parte\s*1\s*[:=]\s*([\d.,]+)\s*s", d)
        if m:
            b["parte1_alvo"] = float(m.group(1).replace(",", "."))
            continue
        m = re.match(r"legendas?\s*[:=]\s*(maiusc|minusc|caixa alta|caixa baixa)", d)
        if m:
            b["legenda_maiusculas"] = m.group(1) in ("maiusc", "caixa alta")
            b["legendas"] = True
            continue
        m = re.match(r"legendas?\s*[:=]\s*(nao|sem|desligad|sim|com|ligad)", d)
        if m:
            b["legendas"] = m.group(1) in ("sim", "com", "ligad")
            continue
        m = re.match(r"transicao\s*[:=]\s*(alternar|escurecer|flash|corte|dissolve|leak|luz)", d)
        if m:
            b["transicao"] = "leak" if m.group(1) == "luz" else m.group(1)
            continue
        m = re.match(r"trilha\s*(?:de\s*)?abertura\s*[:=]\s*(.+)", d)
        if m:
            v = linha.split(":", 1)[-1].strip() if ":" in linha else m.group(1)
            b["trilha_abertura"] = None if dobrar(v) in ("nao", "sem", "nenhuma") else v
            continue
        m = re.match(r"cartela\s*(?:depois\s*d[ae]\s*)?cena\s*(\d+)\s*[:=]\s*(.+)", d)
        if m:
            # cartela de texto depois da cena N: "ANOS DEPOIS... | 3s | efeito suspense | trilha some"
            orig = re.match(r".*?cena\s*\d+\s*[:=]\s*(.+)", linha, flags=re.I)
            k: dict = {}
            for parte in re.split(r"\s*\|\s*", (orig.group(1) if orig else m.group(2)).strip()):
                dp = dobrar(parte)
                mm = re.match(r"([\d.,]+)\s*s(eg(undos)?)?$", dp)
                if mm:
                    k["duracao"] = float(mm.group(1).replace(",", "."))
                elif re.match(r"(sem efeito|efeito\s*(nenhum|nao))", dp):
                    k["efeito"] = ""
                    k["efeito_pedido"] = True
                elif dp.startswith("efeito") or dp.startswith("som "):
                    k["efeito"] = parte.split(None, 1)[1].strip() if " " in parte else ""
                    k["efeito_pedido"] = True
                elif cor_do_texto(dp):
                    k["cor"] = cor_do_texto(dp)
                elif estilo_do_texto(dp):
                    k["estilo"] = estilo_do_texto(dp)
                elif dp.startswith("trilha"):
                    k["trilha"] = "abaixa" if "abaix" in dp else "continua" if ("contin" in dp or "mant" in dp) else "some"
                elif parte and "texto" not in k:
                    k["texto"] = parte.strip().strip('"“”')
            b.setdefault("cartelas", {})[int(m.group(1))] = k
            continue
        m = re.match(r"(?:texto\s+(?:final|do\s+final|no\s+final)|final\s+do\s+video)\s*[:=]\s*(.+)", d)
        if m:
            # "texto final: Fim. | letra branca | fade" -> encerramento (flash -> P&B -> texto) com esse texto
            orig = re.match(r"[^:=]*[:=]\s*(.+)", linha)
            enc = b.setdefault("encerramento", {})
            for parte in re.split(r"\s*\|\s*", (orig.group(1) if orig else m.group(1)).strip()):
                dp = dobrar(parte)
                if cor_do_texto(dp):
                    enc["cor"] = cor_do_texto(dp)
                elif estilo_do_texto(dp):
                    enc["estilo"] = estilo_do_texto(dp)
                elif parte and "texto" not in enc:
                    enc["texto"] = parte.strip().strip('"“”')
            b["continua"] = True
            continue
        m = re.match(r"dividir(?:\s+em\s+partes)?\s*[:=]\s*(sim|nao|com|sem)", d)
        if m:
            b["dividir"] = m.group(1) in ("sim", "com")
            continue
        m = re.match(r"continua(?:\s+no\s+proximo\s+episodio)?(?:\.{3})?\s*[:=]\s*(sim|nao|com|sem)", d)
        if m:
            b["continua"] = m.group(1) in ("sim", "com")
            continue
        m = re.match(r"(?:camera|zoom)\s*[:=]\s*(auto|automatic|sim|nao|sem|parada|desligad)", d)
        if m:
            b["camera_auto"] = m.group(1) in ("auto", "automatic", "sim")
            continue
        m = re.match(r"(?:cor|tratamento de cor|filtro)\s*[:=]\s*(sim|nao|sem|com|ligad|desligad)", d)
        if m:
            b["cor"] = m.group(1) in ("sim", "com", "ligad")
            continue
        m = re.match(r"encerramento\s*[:=]\s*(.+)", d)
        if m:
            enc: dict = {}
            for parte in re.split(r"[;]", m.group(1)):
                parte = parte.strip()
                mm = re.search(r"(?:preto e branco|pb|p&b)\s*([\d.,]+)", parte)
                if mm:
                    enc["pb_duracao"] = float(mm.group(1).replace(",", "."))
                mm = re.search(r"segurar\s*([\d.,]+)", parte)
                if mm:
                    enc["segurar"] = float(mm.group(1).replace(",", "."))
                mm = re.search(r"\bsom\s+(?:do\s+|da\s+)?final\s*[:=]?\s*(.+)", parte)
                if mm:                               # sons na passagem para o P&B (tocam juntos)
                    enc["sons_final"] = lista_de_sons(mm.group(1))
                    continue
                mm = re.search(r"\bsom\s+(?:da\s+|de\s+)?digita\w*\s*[:=]?\s*(.+)", parte)
                if mm:                               # som do texto digitando
                    enc["som_digitacao"] = mm.group(1).strip()
                    continue
                if re.search(r"congel", parte):      # quadro parado em P&B (padrão dos exemplos: o clipe segue andando)
                    enc["pb_movimento"] = False
                mm = re.search(r"cartao\s*(?:de\s*)?([\d.,]+)", parte)
                if mm:                               # duração total do cartão de texto; o "segurar" é calculado
                    enc["cartao_dur"] = float(mm.group(1).replace(",", "."))
                mm = re.search(r"texto\s*[:=]?\s*(.+)", parte)
                if mm:
                    # recupera o texto original (com acentos) da linha bruta
                    orig = re.search(r"texto\s*[:=]?\s*(.+)", linha, flags=re.I)
                    enc["texto"] = (orig.group(1) if orig else mm.group(1)).strip().strip('"')
            b.setdefault("encerramento", {}).update(enc)
            continue
        m = re.match(r"cena\s*(\d+)\s*[:=\-–>→]+\s*(.+)", d)
        if m:
            n = int(m.group(1))
            c = b["cenas"].setdefault(n, {"efeitos": []})
            for instr in re.split(r"\s*;\s*", m.group(2)):
                instr = instr.strip()
                if not instr:
                    continue
                mm = re.match(r"efeitos?\s+(.+?)(?:\s+em\s+([\d.,]+)\s*s?)?(?:\s+volume\s+(-?[\d.,]+)\s*(?:db)?)?$", instr)
                if mm:
                    c["efeitos"].append({"nome": mm.group(1).strip(),
                                         "em": float(mm.group(2).replace(",", ".")) if mm.group(2) else 0.0,
                                         "volume": float(mm.group(3).replace(",", ".")) if mm.group(3) else 0.0})
                    continue
                mm = re.search(r"\bcom\s+(?:o\s+)?(?:efeito|som)(?:\s+sonoro)?\s+(.+)$", instr)
                if mm and instr.startswith("transicao"):
                    c["som_transicao"] = mm.group(1).strip()
                mm = re.match(r"(?:som|efeito)\s+(?:sonoro\s+)?(?:na|da)\s+transicao\s*[:=]?\s*(.+)$|som\s+(?!na\b|da\b)(.+)$", instr)
                if mm:
                    c["som_transicao"] = (mm.group(1) or mm.group(2)).strip()
                    continue
                mm = re.match(r"transicao\s+(escurecer|flash|corte|dissolve|leak|luz)", instr)
                if mm:
                    c["transicao"] = "leak" if mm.group(1) == "luz" else mm.group(1)
                    continue
                mm = re.match(r"trilha\s+(.+)", instr)
                if mm:
                    c["trilha"] = mm.group(1).strip()
                    continue
                if re.match(r"sem\s+corte", instr):
                    c["sem_corte"] = True
                    continue
                mm = re.match(r"inicio\s+([\d.,]+)", instr)
                if mm:
                    c["inicio"] = float(mm.group(1).replace(",", "."))
                    continue
                mm = re.match(r"(?:fim|cortar em)\s+([\d.,]+)", instr)
                if mm:
                    c["fim"] = float(mm.group(1).replace(",", "."))
                    continue
                mm = re.match(r"duracao\s+([\d.,]+)", instr)
                if mm:
                    c["duracao"] = float(mm.group(1).replace(",", "."))
                    continue
                # câmera (medida nos exemplos): zoom in/out lento, impacto, recorte fixo, espelhar, enquadrar
                segurar_zoom = bool(re.search(r"\s+(e\s+)?(segurar|segura|sem voltar|fica)$", instr))
                if segurar_zoom:
                    instr = re.sub(r"\s+(e\s+)?(segurar|segura|sem voltar|fica)$", "", instr)
                # "zoom in no rosto direita" / "zoom out no rosto 0.7 0.35" / "zoom in no rosto" (rosto mais visível)
                rosto_pedido = None
                mr = re.search(r"\s+(?:no|na)\s+(?:rosto|face|personagem)(?:\s+(?:d[aoe]s?\s+)?(.+?))?(?=\s+(?:ate|de|em)\s+[\d.,]|$)", instr)
                if mr and instr.startswith("zoom"):
                    alvo = (mr.group(1) or "").strip()
                    mxy = re.match(r"([\d.,]+)\s+([\d.,]+)$", alvo)
                    if mxy:
                        rosto_pedido = (float(mxy.group(1).replace(",", ".")), float(mxy.group(2).replace(",", ".")))
                    else:
                        rosto_pedido = next((lado for lado in ("esquerda", "direita", "centro") if lado in alvo), "auto")
                    instr = (instr[: mr.start()] + instr[mr.end():]).strip()
                mm = re.match(r"zoom\s+(in|out|impacto|entrar|sair|aproximar|afastar)(?:\s+(?:ate|de|para|em)?\s*([\d.,]+))?"
                              r"(?:\s+em\s+([\d.,]+)\s*s?)?$", instr)
                if mm:
                    tipo = {"entrar": "in", "aproximar": "in", "sair": "out", "afastar": "out"}.get(mm.group(1), mm.group(1))
                    num = float(mm.group(2).replace(",", ".")) if mm.group(2) else None
                    pedido = {"tipo": tipo}
                    if tipo == "impacto":
                        em = mm.group(3) or (mm.group(2) if num is not None and num > 1.6 else None)
                        if em:
                            pedido["em"] = float(em.replace(",", "."))
                        if num is not None and num <= 1.6:
                            pedido["valor"] = num
                    elif num is not None:
                        pedido["valor"] = num
                    if segurar_zoom:
                        pedido["segurar"] = True   # impacto que não volta (gancho que corta para o encerramento)
                    if rosto_pedido:
                        pedido["rosto"] = rosto_pedido
                    c["camera"] = pedido
                    continue
                mm = re.match(r"(?:zoom|close|recorte)\s*([\d.,]+)?\s*(cima|baixo|centro)?$", instr)
                if mm and (mm.group(1) or instr.startswith("close")):
                    c["camera"] = {"tipo": "fixo", "valor": float(mm.group(1).replace(",", ".")) if mm.group(1) else None,
                                   "ancora": mm.group(2) or "centro"}
                    continue
                if re.match(r"(sem zoom|zoom\s+(nao|parado|nenhum)|camera parada)$", instr):
                    c["camera"] = {"tipo": "nenhum"}
                    continue
                if re.match(r"espelhar|espelhad", instr):
                    c["espelhar"] = True
                    continue
                mm = re.match(r"enquadrar\s+([\d.,]+)\s*(?:>|->|→|ate|a)\s*([\d.,]+)", instr)
                if mm:  # deslize lento e linear do recorte 9:16 (como os keyframes da história 2)
                    c["enquadrar"] = ("deslize", float(mm.group(1).replace(",", ".")), float(mm.group(2).replace(",", ".")))
                    continue
                mm = re.match(r"enquadrar\s+(esquerda|direita|centro|seguir|[\d.,]+)", instr)
                if mm:
                    v = mm.group(1)
                    c["enquadrar"] = {"esquerda": 0.25, "direita": 0.75, "centro": 0.5, "seguir": "seguir"}.get(v) or \
                        float(v.replace(",", "."))
                    continue
                # palavra que o transcritor errou: "corrigir desde por 10" (a legenda mostra o texto na tela)
                if re.match(r"corrigir\s", instr):
                    for alvo_c, novo_c in re.findall(r"corrigir\s+(.+?)\s+(?:por|para)\s+([^;]+)", linha, flags=re.I):
                        c.setdefault("corrigir", {})[re.sub(r"[^\w]", "", dobrar(alvo_c))] = novo_c.strip().strip('"“”')
                    continue
                # monetização: silenciar palavra(s) ou trecho, remover a cena
                mm = re.match(r"silenciar\s+([\d.,]+)\s*(?:-|a|ate)\s*([\d.,]+)\s*s?$", instr)
                if mm:
                    c.setdefault("silenciar", []).append((float(mm.group(1).replace(",", ".")), float(mm.group(2).replace(",", "."))))
                    continue
                mm = re.match(r"silenciar\s+(.+)", instr)
                if mm:
                    c.setdefault("silenciar_palavras", []).append(mm.group(1).strip().strip('"“”\''))
                    continue
                if re.match(r"(remover|tirar|excluir)(\s+a)?(\s+cena)?$", instr):
                    c["remover"] = True
                    continue
                if re.match(r"sem (fala|legenda)$", instr):   # ignora a transcrição (frase inventada no silêncio)
                    c["sem_fala"] = True
                    continue
                log(f"   (briefing) instrução não entendida na cena {n}: '{instr}'")
            continue
        log(f"   (briefing) linha não entendida: '{linha}'")
    return b


# ----------------------------------------------------------------------------- biblioteca (trilhas e efeitos)
def listar_audios(pasta: Path) -> list[Path]:
    return sorted([p for p in pasta.rglob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg", ".flac")])


def escolher_trilha(cfg: dict, brief: dict, estilo_cli: str | None, necessario: float, semente: str,
                    duracoes: dict) -> Path | None:
    raiz = Path(cfg["trilha"]["pasta"])
    if not raiz.exists():
        log(f"   pasta de trilhas não encontrada: {raiz}")
        return None
    todas = listar_audios(raiz)
    if not todas:
        return None
    if brief.get("trilha"):
        alvo = dobrar(brief["trilha"])
        melhor = max(todas, key=lambda p: difflib.SequenceMatcher(None, alvo, dobrar(p.stem)).ratio()
                     + (0.5 if alvo in dobrar(p.stem) else 0))
        return melhor
    estilo = dobrar(estilo_cli or brief.get("estilo") or "")
    pasta_estilo = None
    for chave, nome in cfg["trilha"]["estilos"].items():
        if chave in estilo:
            pasta_estilo = nome
            break
    if pasta_estilo is None:
        pasta_estilo = cfg["trilha"]["estilo_padrao"]
        if estilo:
            log(f"   estilo '{estilo}' não reconhecido; usando '{pasta_estilo}'")
    cand = [p for p in todas if dobrar(p.parent.name) == dobrar(pasta_estilo)]
    if not cand:
        cand = todas
    for p in cand:
        if str(p) not in duracoes:
            duracoes[str(p)] = probe(p)["dur"]
    longas = [p for p in cand if duracoes[str(p)] >= necessario]
    rnd = random.Random(semente)
    if cfg["trilha"].get("preferir_longas", True) and longas:
        return rnd.choice(longas)
    return max(cand, key=lambda p: duracoes[str(p)])


def resolver_trilha(cat: dict, pedido: str, clima: dict, necessario: float) -> tuple[Path | None, str]:
    """'Drama 01' -> pasta Drama, trilha 01 (regra do usuário, 30/10/2026); 'suspense' / 'drama' / ... -> escolha pelo
    clima dentro dessa pasta; outro texto -> nome do arquivo. Pedido que não existe para a edição com aviso: nunca
    trocar por outra trilha sem o usuário saber."""
    e = dobrar(pedido)
    m = re.fullmatch(r"(?:trilha\s+)?(\w+?)\s*(?:\bn[ºo.]*\s*|#\s*|-\s*|\btrilha\s+)?0*(\d+)(?:\.mp3)?", e)
    if m:
        pasta_pedida = {"epico": "epic", "epica": "epic"}.get(m.group(1), m.group(1))
        da_pasta = [Path(k) for k in cat.get("trilhas", {}) if dobrar(Path(k).parent.name) == pasta_pedida]
        if da_pasta:
            for t in da_pasta:
                n = re.search(r"\d+", t.stem)
                if n and int(n.group()) == int(m.group(2)):
                    return t, f"pedido no briefing: {t.parent.name} {t.stem}"
            existentes = ", ".join(sorted(t.stem for t in da_pasta))
            erro(f"a trilha '{pedido}' não existe: a pasta {da_pasta[0].parent.name} tem {existentes}")
    if re.fullmatch(r"0*\d+", e):
        erro(f"trilha '{pedido}': diga também a pasta (ex.: Drama {pedido})")
    for chave, pasta in [("suspense", "Suspense"), ("terror", "Suspense"), ("tens", "Suspense"), ("drama", "Drama"),
                         ("trist", "Drama"), ("melanc", "Piano"), ("piano", "Piano"), ("acao", "Epic"), ("epic", "Epic"),
                         ("inspir", "Piano"), ("emocion", "Piano"), ("esperan", "Piano"),
                         ("normal", "Piano"), ("violao", "Piano"), ("calm", "Piano"), ("leve", "Piano")]:
        if not m and (e == chave or e.startswith(chave) or (len(e) <= 12 and chave in e)):
            return trilhas.escolher_por_clima(cat, clima, necessario, pasta_forcada=pasta)
    todas = [Path(k) for k in cat.get("trilhas", {})]
    if not todas:
        return None, "catálogo vazio"
    melhor = max(todas, key=lambda p: difflib.SequenceMatcher(None, e, dobrar(p.stem)).ratio() + (0.5 if e in dobrar(p.stem) else 0))
    if e not in dobrar(melhor.stem) and difflib.SequenceMatcher(None, e, dobrar(melhor.stem)).ratio() < 0.6:
        opcoes = ", ".join(f"{t.parent.name} {t.stem}" for t in sorted(todas, key=lambda t: (t.parent.name, t.stem)))
        erro(f"a trilha '{pedido}' não existe na pasta de trilhas. Opções: {opcoes}")
    return melhor, f"pedido no briefing: '{pedido}' -> {melhor.parent.name} / {melhor.name}"


def _efeito_da_pasta(arquivos: list[Path], pedido: str) -> Path | None:
    """'02' / '#2' = o arquivo de número 2 da pasta; outro texto = parte do nome do arquivo."""
    m = re.fullmatch(r"#?0*(\d+)", pedido.strip())
    if m:
        for a in arquivos:
            n = re.search(r"\d+", a.stem)
            if n and int(n.group()) == int(m.group(1)):
                return a
        return None
    return next((a for a in arquivos if dobrar(pedido) in dobrar(a.name)), None)


def escolher_efeito(cfg: dict, nome: str, arquivo: str | None = None) -> Path | None:
    """'Woosh 02' = pasta woosh, arquivo 02 (regra do usuário, 31/10/2026; 'Woosh/02' também vale). Só o nome da pasta =
    o arquivo 01. Pedido que não existe para a edição com aviso: nunca trocar um som por outro sem o usuário saber."""
    if "/" in nome and not arquivo:
        nome, arquivo = [x.strip() for x in nome.split("/", 1)]
    if not arquivo:
        m = re.fullmatch(r"(.+?)\s+(?:\bn[ºo.]*\s*|#\s*)?(\d+)", nome.strip())
        if m:
            nome, arquivo = m.group(1), m.group(2)
    raiz = Path(cfg["efeitos"]["pasta"])
    if not raiz.exists():
        erro(f"pasta de efeitos não encontrada: {raiz}")
    pastas = [d for d in raiz.iterdir() if d.is_dir()]
    if not pastas:
        return None
    alvo = dobrar(nome)

    def pontos(d: Path) -> float:
        n = dobrar(d.name)
        r = difflib.SequenceMatcher(None, alvo, n).ratio()
        if alvo in n or n in alvo:
            r += 0.6
        # tokens em comum
        ta, tn = set(alvo.split()), set(n.split())
        r += 0.3 * len(ta & tn)
        return r

    melhor = max(pastas, key=pontos)
    if pontos(melhor) < 0.45:
        erro(f"o efeito '{nome}' não existe. Pastas de efeitos: " + ", ".join(sorted(d.name for d in pastas)))
    arquivos = listar_audios(melhor)
    if not arquivos:
        return None
    if arquivo:
        a = _efeito_da_pasta(arquivos, arquivo)
        if not a:
            erro(f"o efeito '{nome} {arquivo}' não existe: a pasta {melhor.name} tem " + ", ".join(x.stem for x in arquivos))
        return a
    return arquivos[0]


def listar_efeitos(cfg: dict, pasta: str, padrao: str | None = None) -> list[Path]:
    """O arquivo `padrao` de uma pasta de efeitos (ou todos, sem padrao); pedido que não existe para com aviso."""
    raiz = Path(cfg["efeitos"]["pasta"])
    alvo = dobrar(pasta)
    for d in raiz.iterdir() if raiz.exists() else []:
        if d.is_dir() and dobrar(d.name) == alvo:
            todos = listar_audios(d)
            if padrao:
                a = _efeito_da_pasta(todos, padrao)
                if not a:
                    erro(f"o som de transição '{pasta} {padrao}' não existe: a pasta {d.name} tem " + ", ".join(x.stem for x in todos))
                return [a]
            return todos
    erro(f"a pasta de efeitos '{pasta}' não existe em {raiz}")
    return []


# ----------------------------------------------------------------------------- legendas (ASS)
def ass_t(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def cor_ass(rrggbb: str, alpha: str = "00") -> str:
    c = rrggbb.strip().lstrip("#").upper()
    return f"&H{alpha}{c[4:6]}{c[2:4]}{c[0:2]}"


def esc_ass(t: str) -> str:
    return t.replace("\\", "/").replace("{", "(").replace("}", ")")


def limpar_palavra(w: str, cfg_leg: dict, maiusculas: bool) -> str:
    t = w.strip().strip('"“”«»()[]')
    rem = cfg_leg.get("remover_pontuacao", ".,;:…")
    while t and t[-1] in rem:
        t = t[:-1]
    while t and t[0] in rem:
        t = t[1:]
    return t.upper() if maiusculas else t


PALAVRAS_DE_LIGACAO = {"a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "em", "no", "na", "nos",
                       "nas", "por", "pelo", "pela", "para", "pra", "com", "sem", "e", "ou", "que", "se", "me", "te", "lhe", "ao",
                       "meu", "minha", "seu", "sua", "nosso", "nossa"}


def agrupar_palavras(palavras: list[dict], max_p: int, pausa: float = 0.8, max_chars: int = 20) -> list[list[dict]]:
    """Divide em frases (pontuação ou pausa) e depois em blocos de até max_p palavras, sem órfãos."""
    frases: list[list[dict]] = []
    cur: list[dict] = []
    for i, w in enumerate(palavras):
        if cur and w["s"] - cur[-1]["e"] > pausa:
            frases.append(cur)
            cur = []
        cur.append(w)
        if w["w"] and w["w"][-1] in ".?!…;:,":
            frases.append(cur)
            cur = []
    if cur:
        frases.append(cur)
    blocos: list[list[dict]] = []
    for fr in frases:
        n, i = len(fr), 0
        while i < n:
            resto = n - i
            if resto <= max_p:
                k = resto
            elif resto == max_p + 1:
                k = math.ceil(resto / 2)
            else:
                k = max_p
            # uma linha só, como nos exemplos: bloco longo demais perde a última palavra
            while k > 1 and len(" ".join(x.get("t") or x["w"] for x in fr[i:i + k])) > max_chars:
                k -= 1
            if k < resto:
                # o bloco não termina em palavra de ligação ("POR / QUE VOCÊ", "DO / SEU FILHO")
                j = k
                while j > 1 and re.sub(r"[^\w]", "", dobrar(fr[i + j - 1]["w"])) in PALAVRAS_DE_LIGACAO:
                    j -= 1
                if j >= 2 or resto - j <= max_p:
                    k = j
            blocos.append(fr[i:i + k])
            i += k
    return blocos


def estilo_legenda(cfg: dict, maiusculas: bool) -> str:
    L = cfg["legenda"]
    H = cfg["video"]["altura"]
    tam = int(L["tamanho"])
    mv = int(H - L["centro_y"] - round(0.46 * tam))
    return ("Style: L,{fonte},{tam},{cor},&H0000FFFF,{contorno_cor},&H80000000,{neg},{ita},0,0,100,100,{esp},0,1,"
            "{contorno},{sombra},2,{ml},{ml},{mv},1").format(
        fonte=L["fonte"], tam=tam, cor=cor_ass(L["cor"]), contorno_cor=cor_ass(L["cor_contorno"]),
        neg=int(L.get("fonte_negrito", 1)), ita=int(L.get("fonte_italico", 1)), esp=L.get("espacamento", 0),
        contorno=L["contorno"], sombra=L["sombra"], ml=L["margem_lateral"], mv=mv)


CABECALHO_ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 1
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{estilo}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def palavras_na_voz(c: dict) -> list[dict]:
    """Tempos das palavras para a legenda, presos à voz medida no áudio do clipe. O transcritor acerta as palavras, mas
    estica as pausas (ex.: "800?" de 0,0 a 1,76 s com a voz só em 0,8 s; "explicação?" até 8,1 s com a voz parando em
    7,22 s). Cada palavra vai para o trecho de voz com que mais se sobrepõe e, dentro dele, o tempo é dividido pelo
    tamanho das palavras. Só a legenda usa isto: os cortes continuam como estão."""
    pal = [dict(w) for w in c["palavras"] if not w.get("silenciada")]
    try:
        import numpy as np
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(c["arquivo"]), "-vn", "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                             capture_output=True).stdout
        a = np.frombuffer(raw, np.float32)
        n = 320  # 20 ms
        db = 20 * np.log10(np.sqrt((a[: len(a) // n * n].reshape(-1, n) ** 2).mean(1)) + 1e-9)
    except Exception:  # noqa — sem medição, fica com os tempos do transcritor
        return pal
    voz = db > (np.percentile(db, 10) + np.percentile(db, 90)) / 2
    trechos, ini = [], None
    for k, v in enumerate(voz):
        if v and ini is None:
            ini = k
        elif not v and ini is not None and not voz[k: k + 6].any():    # buracos de até 0,12 s não separam
            trechos.append((ini * 0.02, k * 0.02))
            ini = None
    if ini is not None:
        trechos.append((ini * 0.02, len(voz) * 0.02))
    por_trecho: dict[int, list[dict]] = {}
    for w in pal:
        sobre = [max(0.0, min(w["e"], b) - max(w["s"], a_)) for a_, b in trechos]
        if sobre and max(sobre) > 0:
            por_trecho.setdefault(sobre.index(max(sobre)), []).append(w)
    for i_t, ws in por_trecho.items():
        a_, b = trechos[i_t]
        total = sum(max(1, len(re.sub(r"[^\w]", "", w["w"]))) for w in ws)
        t = a_
        for w in ws:
            w["s"] = round(t, 3)
            t += (b - a_) * max(1, len(re.sub(r"[^\w]", "", w["w"]))) / total
            w["e"] = round(t, 3)
    return pal


def gerar_legendas_ass(cenas: list[dict], cfg: dict, maiusculas: bool) -> tuple[str, int]:
    L = cfg["legenda"]
    cor_d = cor_ass(L["cor_destaque"])
    cor_n = cor_ass(L["cor"])
    linhas = []
    n_blocos = 0
    for k, c in enumerate(cenas):
        off, ini, dur = c["offset"], c["inicio"], c["dur_final"]
        if k + 1 < len(cenas):
            dur = min(dur, cenas[k + 1]["offset"] - off)   # no dissolve as cenas se sobrepõem: uma legenda por vez
        pal = []
        for w in palavras_na_voz(c):
            txt = limpar_palavra(w["w"], L, maiusculas)
            if not txt:
                continue
            s = off + max(0.0, w["s"] - ini)
            e = off + max(0.0, w["e"] - ini)
            if s >= off + dur:
                continue
            pal.append({"w": w["w"], "t": txt, "s": s, "e": min(e, off + dur)})
        blocos = agrupar_palavras(pal, int(L["max_palavras"]), max_chars=int(L.get("max_caracteres", 20)))
        for bi, bl in enumerate(blocos):
            n_blocos += 1
            inicio = bl[0]["s"]
            prox = blocos[bi + 1][0]["s"] if bi + 1 < len(blocos) else None
            fim = bl[-1]["e"] + float(L["segurar_apos_fala"])
            if prox is not None:
                fim = min(fim, prox)
            fim = min(fim, off + dur)
            textos = [esc_ass(p["t"]) for p in bl]
            for i, p in enumerate(bl):
                ws = p["s"] if i > 0 else inicio
                we = bl[i + 1]["s"] if i + 1 < len(bl) else fim
                if we - ws < 0.02:
                    continue
                partes = []
                for j, t in enumerate(textos):
                    partes.append(f"{{\\c{cor_d}}}{t}{{\\c{cor_n}}}" if j == i else t)
                linhas.append(f"Dialogue: 0,{ass_t(ws)},{ass_t(we)},L,,0,0,0,,{' '.join(partes)}")
    txt = CABECALHO_ASS.format(w=cfg["video"]["largura"], h=cfg["video"]["altura"],
                               estilo=estilo_legenda(cfg, maiusculas)) + "\n".join(linhas) + "\n"
    return txt, n_blocos


def gerar_cartao_ass(cfg: dict, enc: dict, duracao_cartao: float) -> str:
    E = enc
    texto = E["texto"]
    cps = float(E["letras_por_segundo"])
    t0 = float(E["inicio_digitacao"])
    cursor = E.get("cursor", "|")
    cor_cur = cor_ass(E.get("cor_cursor", "FFFFFF"))
    estilo = ("Style: C,{fonte},{tam},{cor},&H0000FFFF,&H00000000,&H00000000,0,1,0,0,100,100,0,0,1,0,0,5,40,40,0,1"
              ).format(fonte=E["fonte"], tam=int(E["tamanho"]), cor=cor_ass(E["cor"]))
    linhas = []
    n = len(texto)
    modo = E.get("estilo") or "digitando"
    cab = CABECALHO_ASS.format(w=cfg["video"]["largura"], h=cfg["video"]["altura"], estilo=estilo)
    if modo in ("fade", "fade in", "fade out"):
        # o cartão inteiro já some com fade_final; aqui só a entrada suave
        fin = 0 if modo == "fade out" else 700
        return cab + f"Dialogue: 0,{ass_t(t0)},{ass_t(duracao_cartao + 1)},C,,0,0,0,,{{\\fad({fin},0)}}{esc_ass(texto)}\n"
    if modo == "revelar":
        K = cfg.get("cartela", {})
        passo = float(K.get("revelar_dur", 1.3)) / max(1, n - 1)
        partes = []
        for i, ch in enumerate(texto):
            a_ = int(round((t0 + i * passo) * 1000))
            b_ = a_ + int(round(float(K.get("suavidade", 0.45)) * 1000))
            partes.append(f"{{\\alpha&HFF&\\blur{float(K.get('desfoque', 6)):g}\\t({a_},{b_},\\alpha&H00&\\blur0)}}{esc_ass(ch)}")
        return cab + f"Dialogue: 0,{ass_t(0)},{ass_t(duracao_cartao + 1)},C,,0,0,0,,{''.join(partes)}\n"
    for i in range(1, n + 1):
        a = t0 + (i - 1) / cps
        b = t0 + i / cps
        parcial = esc_ass(texto[:i])
        linhas.append(f"Dialogue: 0,{ass_t(a)},{ass_t(b)},C,,0,0,0,,{parcial}{{\\c{cor_cur}}}{cursor}")
    linhas.append(f"Dialogue: 0,{ass_t(t0 + n / cps)},{ass_t(duracao_cartao + 1)},C,,0,0,0,,{esc_ass(texto)}")
    return CABECALHO_ASS.format(w=cfg["video"]["largura"], h=cfg["video"]["altura"], estilo=estilo) + "\n".join(linhas) + "\n"


def gerar_cartela_ass(cfg: dict, K: dict, duracao: float) -> str:
    """Cartela entre cenas: texto revelado letra por letra da esquerda para a direita; cada letra sai do transparente
    e desfocado para nítido em `suavidade` s, e as letras se sobrepõem, então a borda da revelação é um degradê."""
    texto = K.get("texto") or ""
    n = max(1, len(texto))
    passo = float(K["revelar_dur"]) / max(1, n - 1)
    estilo = ("Style: K,{fonte},{tam},{cor},&H000000FF,&H00000000,&H00000000,{neg},{ita},0,0,100,100,{esp},0,1,0,0,5,60,60,0,1"
              ).format(fonte=K["fonte"], tam=int(K["tamanho"]), cor=cor_ass(K["cor"]), neg=-1 if K.get("negrito") else 0,
                       ita=-1 if K.get("italico") else 0, esp=K.get("espacamento", 0))
    cab = CABECALHO_ASS.format(w=cfg["video"]["largura"], h=cfg["video"]["altura"], estilo=estilo)
    modo = K.get("estilo") or "revelar"
    ini = float(K["revelar_inicio"])
    fim_visivel = max(ini + 0.8, duracao - float(K.get("fusao", 0.5)))   # antes da fusão com a cena seguinte
    if modo in ("fade", "fade in", "fade out"):
        # fade in: aparece suave e fica até a fusão | fade out: já aparece e some suave | fade: os dois
        fin = 600 if modo in ("fade", "fade in") else 0
        fout = 600 if modo in ("fade", "fade out") else 0
        fim = fim_visivel if fout else duracao + 1
        return cab + f"Dialogue: 0,{ass_t(ini)},{ass_t(fim)},K,,0,0,0,,{{\\fad({fin},{fout})}}{esc_ass(texto)}\n"
    if modo == "digitando":
        # máquina de escrever como o "Continua no Próximo episódio...": letra a letra com cursor branco
        cps = float(cfg["encerramento"]["letras_por_segundo"])
        cur = cor_ass(cfg["encerramento"].get("cor_cursor", "FFFFFF"))
        linhas = []
        for i in range(1, n + 1):
            a, b = ini + (i - 1) / cps, ini + i / cps
            linhas.append(f"Dialogue: 0,{ass_t(a)},{ass_t(b)},K,,0,0,0,,{esc_ass(texto[:i])}{{\\c{cur}}}|")
        linhas.append(f"Dialogue: 0,{ass_t(ini + n / cps)},{ass_t(duracao + 1)},K,,0,0,0,,{esc_ass(texto)}")
        return cab + "\n".join(linhas) + "\n"
    blur = float(K.get("desfoque", 6))
    partes = []
    for i, ch in enumerate(texto):
        t0 = int(round((ini + i * passo) * 1000))
        t1 = t0 + int(round(float(K["suavidade"]) * 1000))
        partes.append(f"{{\\alpha&HFF&\\blur{blur:g}\\t({t0},{t1},\\alpha&H00&\\blur0)}}{esc_ass(ch)}")
    linha = f"Dialogue: 0,{ass_t(0)},{ass_t(duracao + 1)},K,,0,0,0,,{''.join(partes)}"
    return cab + linha + "\n"


# ----------------------------------------------------------------------------- plano
def planejar(pasta: Path, trabalho: Path, cfg: dict, brief: dict, forcar: bool, modelo_local: str) -> list[dict]:
    origem = pasta / "cenas" if (pasta / "cenas").is_dir() else pasta
    clipes = sorted([p for p in origem.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXT], key=numero_natural)
    if not clipes:
        erro(f"nenhum vídeo encontrado em {origem}")
    C = cfg["cortes"]
    cenas = []
    log(f"Cenas encontradas: {len(clipes)}  (transcrevendo falas...)")
    numeros = [numero_natural(p)[0] for p in clipes]
    pelo_nome = len(set(numeros)) == len(numeros) and all(n < 10**9 for n in numeros)
    for pos, p in enumerate(clipes, 1):
        i = numero_natural(p)[0] if pelo_nome else pos   # "cena 20" = arquivo 20, mesmo sem a 19
        ov = brief["cenas"].get(i, {})
        if ov.get("remover"):
            log(f"  cena {i:02d}  {p.name:28s} REMOVIDA (briefing)")
            continue
        pr = probe(p)
        pal = transcrever(p, trabalho, forcar, modelo_local)
        pal = [] if ov.get("sem_fala") else [dict(w) for w in pal if w["e"] > w["s"] - 0.01 and w["s"] < pr["dur"]]
        for w in pal:
            novo_c = (ov.get("corrigir") or {}).get(re.sub(r"[^\w]", "", dobrar(w["w"])))
            if novo_c:
                w["w"] = novo_c + re.sub(r"^\w+", "", w["w"])   # mantém a pontuação grudada na palavra
        # silenciar (monetização): palavras pedidas no briefing viram trechos mudos
        silencio = list(ov.get("silenciar", []))
        for alvo in ov.get("silenciar_palavras", []):
            toks = [re.sub(r"[^\w]", "", dobrar(x)) for x in alvo.split()]
            achou = False
            for k in range(len(pal) - len(toks) + 1):
                if all(re.sub(r"[^\w]", "", dobrar(pal[k + j]["w"])) == toks[j] for j in range(len(toks))):
                    silencio.append((pal[k]["s"] - 0.04, pal[k + len(toks) - 1]["e"] + 0.04))
                    achou = True
            if not achou:
                log(f"   (briefing) cena {i}: não achei '{alvo}' na fala para silenciar")
        for w in pal:
            if any(a <= (w["s"] + w["e"]) / 2 <= b for a, b in silencio):
                w["silenciada"] = True
        nota_corte = ""
        if pal and not ov.get("sem_corte"):
            inicio = max(0.0, pal[0]["s"] - C["antes_da_fala"])
            fim = min(pr["dur"], pal[-1]["e"] + C["depois_da_fala"])
            sobra = pr["dur"] - fim
            if sobra > 0.5 and C.get("estender_se_movimento", True):
                # depois da fala ainda acontece algo na imagem (gesto, saída, câmera)? Compara o movimento do
                # trecho final com o movimento durante a própria fala: só segura se for claramente maior.
                mov_fala = medir_movimento(p, pal[0]["s"], pal[-1]["e"]) or 0.0
                mov = medir_movimento(p, fim, min(pr["dur"], fim + 1.5))
                limiar = max(float(C.get("limiar_movimento", 3.0)), float(C.get("fator_movimento", 1.3)) * mov_fala)
                if mov is not None and mov > limiar:
                    ext = min(sobra, float(C.get("extensao_movimento", 1.2)))
                    fim = min(pr["dur"], fim + ext)
                    nota_corte = f"  (acontece algo depois da fala, movimento {mov:.1f} > {limiar:.1f}: segurei +{ext:.1f}s)"
                elif mov is not None:
                    nota_corte = f"  (aparado {pr['dur'] - fim:.1f}s de tempo morto no fim; movimento {mov:.1f} vs fala {mov_fala:.1f})"
        elif pal:
            inicio, fim = 0.0, pr["dur"]
        else:
            inicio = 0.0
            fim = min(pr["dur"], ov.get("duracao", C["cena_sem_fala_max"]))
            nota_corte = "  (sem fala: mantida)"
        if "inicio" in ov:
            inicio = max(0.0, min(ov["inicio"], pr["dur"] - 0.5))
        if "fim" in ov:
            fim = max(inicio + 0.5, min(ov["fim"], pr["dur"]))
        if "duracao" in ov and pal:
            fim = max(inicio + 0.5, min(inicio + ov["duracao"], pr["dur"]))
        if fim - inicio < C["minimo_cena"]:
            inicio, fim = 0.0, pr["dur"]
        texto = " ".join(w["w"] for w in pal if not w.get("silenciada"))
        cenas.append({"n": i, "arquivo": p, "dur_orig": pr["dur"], "audio": pr["audio"], "w": pr["w"], "h": pr["h"],
                      "palavras": pal, "inicio": round(inicio, 3), "fim": round(fim, 3),
                      "dur_final": round(fim - inicio, 3), "texto": texto, "silenciar": silencio,
                      "efeitos": ov.get("efeitos", []), "transicao_fixa": ov.get("transicao"),
                      "camera_pedida": ov.get("camera"), "espelhar": ov.get("espelhar", False),
                      "som_transicao": ov.get("som_transicao"),
                      "cartela_depois": ({**cfg.get("cartela", {}), **brief["cartelas"][i]}
                                         if i in brief.get("cartelas", {}) else None),
                      "enquadrar_pedido": ov.get("enquadrar"),
                      "trilha_pedida": ov.get("trilha"), "clima": trilhas.clima_das_falas([texto]) if texto else None})
        sil = f"  [silenciado: {', '.join(f'{a:.2f}–{b:.2f}s' for a, b in silencio)}]" if silencio else ""
        log(f"  cena {i:02d}  {p.name:28s} {pr['dur']:5.1f}s -> {inicio:5.2f}–{fim:5.2f} ({fim - inicio:4.1f}s)  "
            f"{'“' + texto[:60] + ('…' if len(texto) > 60 else '') + '”' if texto else '(sem fala)'}{nota_corte}{sil}")
    if not cenas:
        erro("todas as cenas foram removidas no briefing")
    escolher_transicoes(cenas, cfg, brief)
    escolher_camera(cenas, cfg, brief, trabalho)
    return cenas


# picos de amor/saudade onde os exemplos usam a luz quente (leak)
LEXICO_LEAK = ["amo$", "ame$", "amor", "amava", "te amo", "coracao", "saudade", "nunca esqueci", "tarde demais",
               "lugar dela", "lugar dele", "minha vida", "para sempre", "pra sempre", "abraco", "perdao", "te perdoo",
               "devolveu", "voltou pra casa", "voltar pra casa"]


def pico_emocional(texto: str) -> str | None:
    d = " " + dobrar(texto) + " "
    for r in LEXICO_LEAK:
        if re.search(trilhas._padrao(r), d):
            return r.rstrip("$")
    return None


def escolher_transicoes(cenas: list[dict], cfg: dict, brief: dict) -> None:
    """Transição depois de cada cena, como nos exemplos: dissolve quando a fala continua no clipe seguinte,
    luz quente (leak) num pico de amor/saudade, e no resto escurecer/flash alternados."""
    T = cfg["transicoes"]
    padrao = brief.get("transicao", T["padrao"])
    tipos: list[str | None] = [None] * len(cenas)
    ultimo_leak, t = -1e9, 0.0
    for j, c in enumerate(cenas):
        t += c["dur_final"]
        c["motivo_transicao"] = ""
        if c.get("cartela_depois"):
            tipos[j] = "escurecer"
            c["motivo_transicao"] = f"escurece até o preto -> cartela “{c['cartela_depois'].get('texto', '')}”"
            continue
        if c["transicao_fixa"]:
            tipos[j] = c["transicao_fixa"]
            c["motivo_transicao"] = "briefing"
            continue
        if padrao != "alternar" or j == len(cenas) - 1:
            continue
        prox = cenas[j + 1]
        ultima = c["palavras"][-1]["w"] if c["palavras"] else ""
        if T.get("auto_dissolve", True) and ultima and prox["palavras"] and not re.search(r"[.!?…]\W*$", ultima):
            tipos[j] = "dissolve"
            c["motivo_transicao"] = f"fala continua ('{ultima}' sem ponto)"
            continue
        if T.get("auto_leak", True) and j > 0 and t - ultimo_leak >= float(T.get("leak_intervalo_min_s", 40)):
            fim_fala = " ".join(w["w"] for w in c["palavras"][-12:])
            ini_prox = " ".join(w["w"] for w in prox["palavras"][:8])
            achou = pico_emocional(fim_fala + " " + ini_prox)
            if achou:
                tipos[j] = "leak"
                c["motivo_transicao"] = f"pico emocional ('{achou}')"
                ultimo_leak = t
    atual = T.get("primeira", "escurecer")
    for j, c in enumerate(cenas):
        if tipos[j]:
            c["transicao"] = tipos[j]
        elif padrao == "alternar":
            c["transicao"] = atual
            atual = "flash" if atual == "escurecer" else "escurecer"
        else:
            c["transicao"] = padrao


def escolher_camera(cenas: list[dict], cfg: dict, brief: dict, trabalho: Path) -> None:
    """Câmera de cada cena como nos exemplos 2 e 3 (valores em config.json > camera, medidos em camera.py):
    recorte 9:16 que segue a pessoa nos clipes horizontais, zoom base, zoom de impacto na exclamação do gancho e
    zoom in/out lento e linear nas cenas em que a câmera do próprio clipe está parada. O briefing manda mais."""
    C = cfg.get("camera") or {}
    W, H = cfg["video"]["largura"], cfg["video"]["altura"]
    auto = brief.get("camera_auto", C.get("auto", True))
    cache_p = trabalho / "camera.json"
    cache = json.loads(cache_p.read_text(encoding="utf-8")) if cache_p.exists() else {}

    def medido(chave: str, f):
        if chave not in cache:
            cache[chave] = f()
        return cache[chave]
    zb = float(C.get("zoom_base", 1.0))
    for j, c in enumerate(cenas):
        w, h = int(c["w"] or W), int(c["h"] or H)
        cam: dict = {"zoom_base": zb, "espelhar": bool(c.get("espelhar")), "zoom": [], "mira": (0.5, 0.45)}
        c["motivo_camera"] = ""
        horizontal = w / h > W / H + 0.05
        if horizontal:
            ped = c.get("enquadrar_pedido")
            if isinstance(ped, (int, float)):
                cam["enquadrar"] = [(0.0, float(ped))]
            elif isinstance(ped, (tuple, list)) and ped and ped[0] == "deslize":
                cam["enquadrar"] = [(0.0, float(ped[1])), (c["dur_final"], float(ped[2]))]
            elif ped == "seguir" or (ped is None and (C.get("reenquadrar") or {}).get("auto", False)):
                rot = medido(f"rastro:{c['arquivo']}:{c['inicio']}:{c['fim']}",
                             lambda: camera.rastrear(c["arquivo"], c["inicio"], c["fim"], w, h, W, H,
                                                     float((C.get("reenquadrar") or {}).get("velocidade", 0.12))))
                cam["enquadrar"] = [(t, 1 - x if cam["espelhar"] else x) for t, x in rot]
            cam["mira"] = (0.5, 0.42)
        else:
            m = medido(f"rosto:{c['arquivo']}:{c['inicio']}:{c['fim']}",
                       lambda: camera.centro_rosto(c["arquivo"], (c["inicio"] + c["fim"]) / 2, w, h))
            if m:
                px, py = m
                cam["mira"] = (min(0.7, max(0.3, 1 - px if cam["espelhar"] else px)), min(0.55, max(0.3, py)))
        d = c["dur_final"]
        ped = c.get("camera_pedida") or {}
        if ped:
            tipo = ped["tipo"]
            if tipo == "fixo":
                cam["zoom"] = camera.plano_zoom("fixo", d, C, valor=ped.get("valor"))
                anc = ped.get("ancora", "centro")
                if anc in ("cima", "baixo"):
                    cam["mira"] = (0.5, 0.0 if anc == "cima" else 1.0)
            elif tipo in ("in", "out", "impacto"):
                ro = ped.get("rosto")
                if ro:
                    # zoom no rosto do personagem: o ponto fixo do zoom é esse rosto (ele cresce no lugar)
                    if isinstance(ro, (tuple, list)):
                        px, py = float(ro[0]), float(ro[1])
                    else:
                        t_ref = c["inicio"] + (0.75 if tipo == "in" else 0.25) * d
                        rs = medido(f"rostos:{c['arquivo']}:{t_ref:.2f}",
                                    lambda: camera.rostos(c["arquivo"], t_ref, w, h))
                        if cam["espelhar"]:
                            rs = sorted([(1 - x, y, v) for x, y, v in rs], key=lambda r: r[0])
                        if not rs:
                            px, py = cam["mira"]
                        elif ro == "esquerda":
                            px, py = rs[0][0], rs[0][1]
                        elif ro == "direita":
                            px, py = rs[-1][0], rs[-1][1]
                        elif ro == "centro":
                            px, py = min(rs, key=lambda r: abs(r[0] - 0.5))[:2]
                        else:
                            px, py = max(rs, key=lambda r: r[2])[:2]
                    cam["mira"] = (min(0.88, max(0.12, px)), min(0.75, max(0.12, py)))
                pal = [dict(w_, e_rel=w_["e"] - c["inicio"]) for w_ in c["palavras"]
                       if c["inicio"] <= w_["s"] < c["fim"] and not w_.get("silenciada")]
                em = ped.get("em")
                if tipo == "impacto" and em is None:
                    em = camera.momento_exclamacao(pal)
                cam["zoom"] = camera.plano_zoom(tipo, d, C, em=em, valor=ped.get("valor"), segurar=bool(ped.get("segurar")))
            c["motivo_camera"] = "briefing"
        elif auto and j == 0 and C.get("impacto_no_gancho", True):
            pal = [dict(w_, e_rel=w_["e"] - c["inicio"]) for w_ in c["palavras"]
                   if c["inicio"] <= w_["s"] < c["fim"] and not w_.get("silenciada")]
            em = camera.momento_exclamacao(pal)
            if em is not None and 1.0 < em < d - 0.3:
                cam["zoom"] = camera.plano_zoom("impacto", d, C, em=em)
                c["motivo_camera"] = f"gancho: impacto na exclamação ({em:.1f}s)"
        c["camera"] = cam
    # zoom in/out lento nas cenas paradas, como na história 2 (~25% das cenas, priorizando as mais emotivas)
    if auto and C.get("zoom_lento_auto", True):
        cands = []
        for j, c in enumerate(cenas):
            if j == 0 or c.get("camera_pedida") or c["camera"]["zoom"] or c["dur_final"] < 3.0 or not c["texto"]:
                continue
            if c["camera"].get("enquadrar") and len(c["camera"]["enquadrar"]) > 1:
                continue  # o recorte já está andando atrás da pessoa
            mc = medido(f"cam:{c['arquivo']}:{c['inicio']}:{c['fim']}",
                        lambda: camera.medir_camera(c["arquivo"], c["inicio"], c["fim"], int(c["w"] or W), int(c["h"] or H)))
            c["camera_do_clipe"] = mc
            if not mc or not mc["parada"]:
                continue
            notas = (c.get("clima") or {}).get("notas", {})
            emoc = 1.0 if pico_emocional(c["texto"]) else 0.0
            peso = (c.get("clima") or {}).get("intensidade", 0) + emoc + 0.3 * ("?" in c["texto"][-3:])
            sai = c["texto"].rstrip().endswith("?") or (notas.get("esperanca", 0) + notas.get("calma", 0)
                                                        > notas.get("tristeza", 0) + notas.get("tensao", 0) + 0.5)
            cands.append((peso, j, "out" if sai else "in"))
        n_max = max(1, round(float(C.get("fracao_zoom_lento", 0.25)) * len(cenas)))
        escolhidos = sorted(sorted(cands, reverse=True)[:n_max], key=lambda x: x[1])
        ant_j, ant_dir = -9, ""
        for peso, j, direcao in escolhidos:
            if j == ant_j + 1 and direcao == ant_dir:
                direcao = "out" if direcao == "in" else "in"
            c = cenas[j]
            d = c["dur_final"]
            Z = C["zoom_in"] if direcao == "in" else C["zoom_out"]
            valor = 1 + min(float(Z["max"]) - 1, float(Z["taxa_s"]) * d)
            c["camera"]["zoom"] = camera.plano_zoom(direcao, d, C, valor=valor)
            c["motivo_camera"] = (f"zoom {direcao} {'1.00→' + format(valor, '.2f') if direcao == 'in' else format(valor, '.2f') + '→1.00'}"
                                  f" (câmera do clipe parada; {'pergunta/alívio' if direcao == 'out' else 'fala emotiva'})")
            ant_j, ant_dir = j, direcao
    cache_p.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    for c in cenas:
        z = c["camera"]["zoom"]
        if z and not c["motivo_camera"].startswith("zoom"):
            if len(z) == 1:
                c["motivo_camera"] = (c["motivo_camera"] + " " if c["motivo_camera"] else "") + f"recorte fixo {z[0][1]:.2f}"
            else:
                c["motivo_camera"] = (c["motivo_camera"] + ": " if c["motivo_camera"] else "") + \
                    " → ".join(f"{v:.2f}@{t:.1f}s" for t, v in z)
        if (c.get("camera_pedida") or {}).get("rosto"):
            mx, my = c["camera"]["mira"]
            c["motivo_camera"] += f" no rosto ({c['camera_pedida']['rosto'] if isinstance(c['camera_pedida']['rosto'], str) else 'posição pedida'}: x {mx:.2f}, y {my:.2f})"
        if c["camera"].get("espelhar"):
            c["motivo_camera"] += " espelhada"
        enq = c["camera"].get("enquadrar")
        if enq and len(enq) > 1:
            c["motivo_camera"] += (f" recorte 9:16 deslizando {enq[0][1]:.2f}→{enq[-1][1]:.2f}" if len(enq) == 2 else
                                   f" recorte 9:16 seguindo a pessoa ({len(enq)} pontos)")
        elif enq and abs(enq[0][1] - 0.5) > 0.01:
            c["motivo_camera"] += f" recorte 9:16 em {enq[0][1]:.2f}"


def folha_cenas_brutas(cenas: list[dict], trabalho: Path) -> Path | None:
    """Dois quadros de cada clipe original (30% e 70% do trecho usado), 10 cenas por linha, na ordem. Serve para o
    diretor achar texto/legenda/marca d'água gravados pela IA (na história 3 o clipe veio com "Toma!" escrito e o
    usuário deu zoom 1,13 para tirar) — corrija com `cena N: zoom 1.13` ou `cena N: zoom 1.1 cima`."""
    try:
        import numpy as np
    except ImportError:
        return None
    tw, th = 180, 320
    tiles = []
    for c in cenas:
        col = []
        for frac in (0.3, 0.7):
            t = c["inicio"] + frac * c["dur_final"]
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", fmt(t), "-i", str(c["arquivo"]), "-frames:v", "1", "-vf",
                                  f"scale={tw}:{th}:force_original_aspect_ratio=decrease,pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2",
                                  "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
            q = np.frombuffer(raw, np.uint8)
            col.append(q.reshape(th, tw, 3) if q.size == th * tw * 3 else np.zeros((th, tw, 3), np.uint8))
        tile = np.concatenate([col[0], np.full((6, tw, 3), 255, np.uint8), col[1]], 0)
        tiles.append(np.pad(tile, ((0, 10), (0, 6), (0, 0)), constant_values=40))
    if not tiles:
        return None
    por_linha = 10
    while len(tiles) % por_linha:
        tiles.append(np.full_like(tiles[0], 40))
    linhas = [np.concatenate(tiles[i:i + por_linha], 1) for i in range(0, len(tiles), por_linha)]
    img = np.concatenate(linhas, 0)
    out = trabalho / "cenas_brutas.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{img.shape[1]}x{img.shape[0]}",
                    "-i", "-", str(out)], input=img.tobytes())
    return out if out.exists() else None


def grade_cenas(cenas: list[dict], trabalho: Path, cfg: dict) -> Path | None:
    """Começo (15%) e fim (85%) de cada cena, já enquadrados em 9:16, com grade de 10% e as coordenadas.
    O diretor acha o rosto do personagem pedido e escreve `cena N: zoom in no rosto X Y`: para zoom in use a posição
    do rosto no FIM da cena; para zoom out, no COMEÇO (o clipe do gerador pode andar e mudar o rosto de lugar)."""
    try:
        import numpy as np
    except ImportError:
        return None
    W, H = 270, 480
    fonte = "C\\:/Windows/Fonts/arial.ttf"
    tiles = []
    for c in cenas:
        w, h = int(c["w"] or 1080), int(c["h"] or 1920)
        s_ = max(W / w, H / h)
        sw, sh = int(round(w * s_ / 2)) * 2, int(round(h * s_ / 2)) * 2
        par = []
        for frac, rot in ((0.15, "comeco"), (0.85, "fim")):
            t = c["inicio"] + frac * c["dur_final"]
            vf = [f"scale={sw}:{sh}", f"crop={W}:{H}", "drawgrid=w=iw/10:h=ih/10:t=1:c=white@0.35"]
            for i in range(1, 10):
                vf.append(f"drawtext=fontfile='{fonte}':text='{i / 10:.1f}':x={i * W // 10 - 9}:y=2:fontsize=10:"
                          f"fontcolor=yellow:box=1:boxcolor=black@0.6")
                vf.append(f"drawtext=fontfile='{fonte}':text='{i / 10:.1f}':x=2:y={i * H // 10 - 5}:fontsize=10:"
                          f"fontcolor=yellow:box=1:boxcolor=black@0.6")
            vf.append(f"drawtext=fontfile='{fonte}':text='cena {c['n']} {rot}':x=(w-tw)/2:y=h-22:fontsize=15:"
                      f"fontcolor=white:box=1:boxcolor=black@0.7")
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", fmt(t), "-i", str(c["arquivo"]), "-frames:v", "1",
                                  "-vf", ",".join(vf), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
            q = np.frombuffer(raw, np.uint8)
            par.append(q.reshape(H, W, 3) if q.size == H * W * 3 else np.zeros((H, W, 3), np.uint8))
        tiles.append(np.pad(np.concatenate(par, 1), ((0, 8), (0, 12), (0, 0)), constant_values=40))
    if not tiles:
        return None
    por_linha = 3
    while len(tiles) % por_linha:
        tiles.append(np.full_like(tiles[0], 40))
    img = np.concatenate([np.concatenate(tiles[i:i + por_linha], 1) for i in range(0, len(tiles), por_linha)], 0)
    out = trabalho / "grade_cenas.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{img.shape[1]}x{img.shape[0]}",
                    "-i", "-", str(out)], input=img.tobytes())
    return out if out.exists() else None


def calcular_offsets(cenas: list[dict], cfg: dict) -> float:
    """Início de cada cena no vídeo (o dissolve sobrepõe as duas cenas); devolve a duração do conteúdo."""
    dd_cfg = float(cfg["transicoes"].get("dissolve", {}).get("duracao", 0.5))
    t = 0.0
    for j, c in enumerate(cenas):
        c["sobrepor"] = 0.0
        K = cenas[j - 1].get("cartela_depois") if j > 0 else None
        if K:
            # cartela entre as cenas: começa no preto e funde (xfade) na cena seguinte
            cenas[j - 1]["cartela_ini"] = round(t, 3)
            t += float(K["duracao"])
            c["sobrepor"] = round(min(float(K["fusao"]), 0.4 * c["dur_final"], float(K["duracao"]) / 2), 3)
            t -= c["sobrepor"]
        elif j > 0 and cenas[j - 1]["transicao"] == "dissolve":
            c["sobrepor"] = round(min(dd_cfg, 0.4 * min(cenas[j - 1]["dur_final"], c["dur_final"])), 3)
            t -= c["sobrepor"]
        c["offset"] = round(t, 3)
        t += c["dur_final"]
    return round(t, 3)


def dividir(cenas: list[dict], cfg: dict, brief: dict) -> int:
    n = len(cenas)
    if n < 2:
        return n
    if not brief.get("parte1_cena") and not brief.get("parte1_alvo") and \
            not brief.get("dividir", cfg["partes"].get("dividir", True)):
        return n   # um vídeo só (padrão desde 27/10/2026); dividir só quando o usuário pedir
    if brief.get("parte1_cena"):
        ult = int(brief["parte1_cena"])
        pos = next((i + 1 for i, c in enumerate(cenas) if c["n"] >= ult), n)
        return max(1, min(n, pos))   # = n: a história toda é a Parte 1 (a Parte 2 vem depois)
    alvo = float(brief.get("parte1_alvo", cfg["partes"]["parte1_alvo_s"]))
    minimo2 = float(cfg["partes"]["parte2_minimo_s"])
    acum = 0.0
    melhor, melhor_d = 1, 1e9
    total = sum(c["dur_final"] for c in cenas)
    for k in range(1, n):
        acum += cenas[k - 1]["dur_final"]
        if total - acum < minimo2 and k > 1:
            break
        d = abs(acum - alvo)
        if d < melhor_d:
            melhor, melhor_d = k, d
    return melhor


# ----------------------------------------------------------------------------- render
def filtro_normalizar(cfg: dict) -> str:
    W, H, F = cfg["video"]["largura"], cfg["video"]["altura"], cfg["video"]["fps"]
    return (f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,"
            f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={F},format=yuv420p")


def codificador(cfg: dict, trabalho: Path) -> list[str]:
    V = cfg["video"]
    cache = trabalho / "codec.txt"
    escolha = V.get("codec", "auto")
    if escolha == "auto":
        if cache.exists():
            escolha = cache.read_text().strip()
        else:
            p = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2:r=30",
                                "-c:v", "h264_nvenc", "-f", "null", "-"], capture_output=True)
            escolha = "nvenc" if p.returncode == 0 else "x264"
            cache.write_text(escolha)
    tags =["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]  # como os exemplos
    if escolha == "nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", str(V["qualidade_nvenc_cq"]),
                "-b:v", "0", "-maxrate", "24M", "-bufsize", "48M", "-profile:v", "high", "-pix_fmt", "yuv420p"] + tags
    return ["-c:v", "libx264", "-preset", "medium", "-crf", str(V["qualidade_x264_crf"]), "-profile:v", "high",
            "-pix_fmt", "yuv420p"] + tags


def caminho_filtro(p: Path) -> str:
    """caminho para dentro de um filtro ffmpeg (aspas simples, ':' escapado)."""
    s = str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return f"'{s}'"


def render_parte(num: int, cenas: list[dict], cfg: dict, brief: dict, trabalho: Path, saida: Path,
                 segmentos: list[dict], final_parte1: bool, maiusculas: bool, estado: dict) -> dict:
    """segmentos: [{"inicio": s, "arquivo": Path, "offset": s, "duracao_trilha": s, "por_que": str}] em ordem."""
    V, T, E, EF, TR = cfg["video"], cfg["transicoes"], dict(cfg["encerramento"]), cfg["efeitos"], cfg["trilha"]
    E.update(brief.get("encerramento", {}))
    W, H, F = V["largura"], V["altura"], V["fps"]
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats"]
    n_in = 0

    def add_input(*a: str) -> int:
        nonlocal n_in
        args.extend(a)
        n_in += 1
        return n_in - 1

    linhas: list[str] = []
    conteudo = calcular_offsets(cenas, cfg)
    LK = T.get("leak", {})

    def luz_quente(rampa: str) -> str:
        """Light leak como nos exemplos: luz quente somada à imagem (vermelho -> laranja -> amarelo-branco no pico).
        rampa = expressão em t que vai de 0 (sem luz) a 1 (pico)."""
        k = f"clip({rampa},0,1)"
        return (f"eq=eval=frame:brightness='{LK.get('brilho', 0.6)}*{k}*{k}':saturation='1+0.4*{k}':"
                f"gamma_r='1+{LK.get('vermelho', 2.0)}*{k}':gamma_g='1+{LK.get('verde', 0.9)}*{k}*{k}':"
                f"gamma_b='max(0.2,1-0.5*{k})'")

    # ---- cenas
    m = len(cenas)
    for j, c in enumerate(cenas):
        d = c["dur_final"]
        vi = add_input("-ss", fmt(c["inicio"]), "-t", fmt(d), "-i", str(c["arquivo"]))
        ai = vi if c["audio"] else add_input("-f", "lavfi", "-t", fmt(d), "-i", "anullsrc=r=44100:cl=stereo")
        fades = []
        esc = min(1.0, d / 4)  # cenas muito curtas: encurta os fades
        if j == 0:
            if T.get("abertura_fade", 0) > 0:
                fades.append(f"fade=t=in:st=0:d={fmt(T['abertura_fade'] * esc)}")
        elif cenas[j - 1].get("cartela_depois"):
            pass   # vem da cartela: a fusão (xfade) já faz a entrada, e a cena entra andando
        else:
            prev = cenas[j - 1]["transicao"]
            if prev == "escurecer":
                fades.append(f"fade=t=in:st={fmt(T['escurecer']['preto'] * esc)}:d={fmt(T['escurecer']['entrada'] * esc)}")
            elif prev == "flash":
                fades.append(f"fade=t=in:st={fmt(T['flash']['branco'] * esc)}:d={fmt(T['flash']['entrada'] * esc)}:color=white")
            elif prev == "leak":
                fades.append(luz_quente(f"1-t/{fmt(T['leak']['entrada'] * esc)}"))
        if j == m - 1:
            if final_parte1:
                fs = E["flash_saida"]
                fades.append(f"fade=t=out:st={fmt(d - fs)}:d={fmt(fs)}:color=white")
            elif T.get("fechamento_fade", 0) > 0:
                fo = T["fechamento_fade"] * esc
                fades.append(f"fade=t=out:st={fmt(d - fo)}:d={fmt(fo)}")
        else:
            tr = c["transicao"]
            if c.get("cartela_depois"):
                so = float(c["cartela_depois"]["escurecer_antes"]) * esc   # escurece até o preto da cartela
                fades.append(f"fade=t=out:st={fmt(d - so)}:d={fmt(so)}")
            elif tr == "escurecer":
                so = T["escurecer"]["saida"] * esc
                fades.append(f"fade=t=out:st={fmt(d - so)}:d={fmt(so)}")
            elif tr == "flash":
                so = T["flash"]["saida"] * esc
                fades.append(f"fade=t=out:st={fmt(d - so)}:d={fmt(so)}:color=white")
            elif tr == "leak":
                so = T["leak"]["saida"] * esc
                fades.append(luz_quente(f"(t-{fmt(d - so)})/{fmt(so)}"))
        linhas.append(f"[{vi}:v]{camera.filtro_camera(c, cfg)}" + ("," + ",".join(fades) if fades else "") + f"[v{j}]")
        mudo = "".join(f",volume=enable='between(t,{fmt(max(0.0, a - c['inicio']))},{fmt(b - c['inicio'])})':volume=0"
                       for a, b in c.get("silenciar", []) if b > c["inicio"] and a < c["fim"])
        linhas.append(f"[{ai}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                      f"atrim=0:{fmt(d)},asetpts=PTS-STARTPTS{mudo},afade=t=in:st=0:d=0.02,"
                      f"afade=t=out:st={fmt(max(0, d - 0.03))}:d=0.03[a{j}]")
        K = c.get("cartela_depois")
        if K and j < m - 1:
            # cartela de texto depois desta cena (fundo preto, letras reveladas em degradê da esquerda para a direita)
            dk = float(K["duracao"])
            k_nome = f"cartela_parte{num}_cena{c['n']}.ass"
            (trabalho / k_nome).write_text(gerar_cartela_ass(cfg, K, dk), encoding="utf-8")
            ki = add_input("-f", "lavfi", "-t", fmt(dk), "-i", f"color=c=black:s={W}x{H}:r={F}")
            kai = add_input("-f", "lavfi", "-t", fmt(dk), "-i", "anullsrc=r=44100:cl=stereo")
            linhas.append(f"[{ki}:v]format=yuv420p,ass=filename={k_nome},setsar=1[vk{j}]")
            linhas.append(f"[{kai}:a]aformat=sample_fmts=fltp:channel_layouts=stereo[ak{j}]")
    # cenas ligadas por dissolve (ou pela fusão da cartela) viram um bloco (xfade/acrossfade); os blocos são concatenados
    blocos: list[list] = []

    def juntar(v: str, a: str, dur: float, sobre: float, tag: str, curva_entrada: str = "tri") -> None:
        if blocos and sobre > 0:
            v_ant, a_ant, dur_ant = blocos[-1]
            linhas.append(f"{v_ant}{v}xfade=transition=fade:duration={fmt(sobre)}:offset={fmt(dur_ant - sobre)}[xv{tag}]")
            linhas.append(f"{a_ant}{a}acrossfade=d={fmt(sobre)}:c1=tri:c2={curva_entrada}[xa{tag}]")
            blocos[-1] = [f"[xv{tag}]", f"[xa{tag}]", dur_ant + dur - sobre]
        else:
            blocos.append([v, a, dur])
    for j, c in enumerate(cenas):
        depois_cartela = j > 0 and bool(cenas[j - 1].get("cartela_depois"))
        fala_logo = any(c["inicio"] <= w_["s"] < c["inicio"] + c["sobrepor"] for w_ in c["palavras"] if not w_.get("silenciada"))
        # depois da cartela (muda) ou com a fala já no começo da cena, o áudio entra cheio: sem fade na primeira palavra
        juntar(f"[v{j}]", f"[a{j}]", c["dur_final"], c["sobrepor"] if j > 0 else 0.0, str(j),
               "nofade" if depois_cartela or fala_logo else "tri")
        if c.get("cartela_depois") and j < m - 1:
            juntar(f"[vk{j}]", f"[ak{j}]", float(c["cartela_depois"]["duracao"]), 0.0, f"k{j}")
    if len(blocos) == 1:
        linhas.append(f"{blocos[0][0]}null[vcat]")
        linhas.append(f"{blocos[0][1]}anull[acat]")
    else:
        linhas.append("".join(b[0] + b[1] for b in blocos) + f"concat=n={len(blocos)}:v=1:a=1[vcat][acat]")

    # ---- legendas (desligadas por padrão desde 26/10/2026, como na história 3; "legenda: sim" no briefing liga)
    n_blocos = 0
    if brief.get("legendas", cfg["legenda"].get("ativa", True)):
        ass_txt, n_blocos = gerar_legendas_ass(cenas, cfg, maiusculas)
        ass_nome = f"legendas_parte{num}.ass"
        (trabalho / ass_nome).write_text(ass_txt, encoding="utf-8")
        pasta_fontes = HERE / cfg["legenda"].get("pasta_fontes", "fonts")
        fontsdir = f":fontsdir={caminho_filtro(pasta_fontes)}" if pasta_fontes.is_dir() and any(pasta_fontes.iterdir()) else ""
        linhas.append(f"[vcat]ass=filename={ass_nome}{fontsdir}[vcap]")
    else:
        linhas.append("[vcat]null[vcap]")

    # ---- encerramento da parte 1
    total = conteudo
    eventos_sfx: list[tuple[float, Path, float, float | None]] = []  # (tempo, arquivo, pico_db, duracao_loop)
    if final_parte1:
        ult = cenas[-1]
        pb = float(E["pb_duracao"])
        resto = ult["dur_orig"] - ult["fim"]
        if E.get("pb_movimento", True) and resto > 0.3:
            # como nos exemplos: o clipe continua andando em P&B (o tempo morto aparado vira o encerramento);
            # se faltar imagem, câmera lenta até pb_lento_max e depois segura o último quadro
            lento = min(float(E.get("pb_lento_max", 2.0)), max(1.0, pb / resto))
            ci = add_input("-ss", fmt(ult["fim"]), "-i", str(ult["arquivo"]))
            # mesmo enquadramento/zoom em que a cena parou (sem pulo na imagem)
            fonte_pb = (f"[{ci}:v]{camera.filtro_camera(ult, cfg, fixo_em=ult['dur_final'])},setpts={lento:.3f}*(PTS-STARTPTS),fps={F},"
                        f"tpad=stop_mode=clone:stop_duration={fmt(pb)},trim=duration={fmt(pb)},setpts=PTS-STARTPTS,")
        else:
            quadro = trabalho / f"congelado_parte{num}.png"
            tq = max(ult["inicio"], ult["fim"] - 0.08)
            run(["ffmpeg", "-y", "-v", "error", "-ss", fmt(tq), "-i", str(ult["arquivo"]), "-frames:v", "1",
                 "-vf", camera.filtro_camera(ult, cfg, fixo_em=ult["dur_final"]), str(quadro)])
            ci = add_input("-loop", "1", "-framerate", str(F), "-t", fmt(pb), "-i", str(quadro))
            fonte_pb = f"[{ci}:v]"
        cai = add_input("-f", "lavfi", "-t", fmt(pb), "-i", "anullsrc=r=44100:cl=stereo")
        rot, zoom = float(E["rotacao_graus"]), float(E["zoom"])
        linhas.append(
            f"{fonte_pb}hue=s=0,scale={W * 2}:{H * 2}:flags=lanczos,"
            f"rotate=a='(PI/180)*{rot}*t/{fmt(pb)}':c=black,"
            # zoom sem tremer: o zoompan arredonda o recorte para pixels inteiros e numa imagem congelada isso aparece
            + camera.filtro_zoom_suave(f"(1+{zoom}*in/{int(pb * F)})") +
            f",scale={W}:{H}:flags=area,setsar=1,fps={F},"
            f"format=yuv420p,fade=t=in:st=0:d={fmt(E['flash_entrada'])}:color=white,"
            f"fade=t=out:st={fmt(pb - E['fade_preto'])}:d={fmt(E['fade_preto'])}[vbw]")
        linhas.append(f"[{cai}:a]aformat=sample_fmts=fltp:channel_layouts=stereo[abw]")
        texto = E["texto"]
        modo_final = E.get("estilo") or "digitando"
        digitacao = (len(texto) / float(E["letras_por_segundo"]) if modo_final == "digitando" else
                     0.7 if modo_final.startswith("fade") else
                     float(cfg.get("cartela", {}).get("revelar_dur", 1.3)) + float(cfg.get("cartela", {}).get("suavidade", 0.45)))
        cartao = float(E["inicio_digitacao"]) + digitacao + float(E["segurar"]) + float(E["fade_final"])
        if E.get("cartao_dur"):
            cartao = max(float(E["inicio_digitacao"]) + digitacao + float(E["fade_final"]) + 0.3, float(E["cartao_dur"]))
        card_nome = f"cartao_parte{num}.ass"
        (trabalho / card_nome).write_text(gerar_cartao_ass(cfg, E, cartao), encoding="utf-8")
        ki = add_input("-f", "lavfi", "-t", fmt(cartao), "-i", f"color=c=black:s={W}x{H}:r={F}")
        kai = add_input("-f", "lavfi", "-t", fmt(cartao), "-i", "anullsrc=r=44100:cl=stereo")
        linhas.append(f"[{ki}:v]format=yuv420p,ass=filename={card_nome},"
                      f"fade=t=out:st={fmt(cartao - E['fade_final'])}:d={fmt(E['fade_final'])}[vcard]")
        linhas.append(f"[{kai}:a]aformat=sample_fmts=fltp:channel_layouts=stereo[acard]")
        linhas.append("[vcap][acat][vbw][abw][vcard][acard]concat=n=3:v=1:a=1[vall][adial]")
        total = round(conteudo + pb + cartao, 3)
        # efeitos do encerramento: só os pedidos (regra do usuário, 31/10/2026). Os picos caem juntos no ponto branco.
        for nome_som in E.get("sons_final") or []:
            ef = escolher_efeito(cfg, nome_som)
            r_ = regra_do_som(cfg, ef)
            eventos_sfx.append((quando_tocar(r_, ef, conteudo, estado), ef, float(r_["pico_db"]), None))
        if E.get("som_digitacao"):
            ef = escolher_efeito(cfg, E["som_digitacao"])
            eventos_sfx.append((conteudo + pb + float(E["inicio_digitacao"]), ef, regra_do_som(cfg, ef)["pico_db"],
                                digitacao if EF["digitacao"].get("repetir", True) else None))
    else:
        linhas.append("[vcap]null[vall]")
        linhas.append("[acat]anull[adial]")

    # ---- efeito sonoro nas transições e cartelas: SÓ quando o usuário manda (regra de 31/10/2026); sem pedido, sem som.
    # O pico do som cai no ponto preto/branco/meio do dissolve.
    for j in range(1, len(cenas)):
        K = cenas[j - 1].get("cartela_depois")
        if K:
            ef = escolher_efeito(cfg, K["efeito"]) if K.get("efeito_pedido") and K.get("efeito") else None
            if ef and K.get("estilo") == "digitando" and "teclado" in dobrar(ef.parent.name):
                # teclado só enquanto as letras aparecem
                t_dig = len(K.get("texto") or "") / float(cfg["encerramento"]["letras_por_segundo"])
                eventos_sfx.append((cenas[j - 1]["cartela_ini"] + float(K.get("revelar_inicio", 0.25)), ef,
                                    regra_do_som(cfg, ef)["pico_db"], max(0.3, t_dig)))
            elif ef:
                # só durante a cartela: começa no preto e termina quando a cena seguinte acabou de entrar
                eventos_sfx.append((cenas[j - 1]["cartela_ini"], ef, float(K.get("efeito_pico_db", -20)),
                                    float(K["duracao"])))
            continue
        tipo = cenas[j - 1]["transicao"]
        pedido = cenas[j - 1].get("som_transicao")
        if not pedido or dobrar(pedido) in ("nenhum", "sem", "nao", "sem som", "sem efeito"):
            continue
        ponto = cenas[j]["offset"] + (cenas[j]["sobrepor"] / 2 if tipo == "dissolve" else 0.0)
        for nome_som in lista_de_sons(pedido):
            arq = escolher_efeito(cfg, nome_som)
            r_ = regra_do_som(cfg, arq)
            eventos_sfx.append((quando_tocar(r_, arq, ponto, estado), arq, float(r_["pico_db"]), None))

    # ---- efeitos por cena (briefing)
    for c in cenas:
        for e in c["efeitos"]:
            ef = escolher_efeito(cfg, e["nome"])
            if not ef:
                log(f"   efeito não encontrado para '{e['nome']}' (cena {c['n']})")
                continue
            eventos_sfx.append((c["offset"] + float(e.get("em", 0.0)), ef, EF["pico_db"] + float(e.get("volume", 0.0)), None))

    # ---- áudio: ganho da fala
    lufs_pond = 0.0
    dur_pond = 0.0
    for c in cenas:
        if not c["audio"] or not c["palavras"]:
            continue
        k = f"lufs:{c['arquivo']}:{c['inicio']}:{c['fim']}"
        if k not in estado:
            estado[k] = medir_lufs(c["arquivo"], c["inicio"], c["dur_final"])
        L = estado[k]
        if L is None or L < -60:
            continue
        lufs_pond += c["dur_final"] * (10 ** (L / 10))
        dur_pond += c["dur_final"]
    lufs_fala = 10 * math.log10(lufs_pond / dur_pond) if dur_pond > 0 else -16.0
    ganho_fala = max(-12.0, min(18.0, TR["fala_lufs"] - lufs_fala))

    mix_in = ["[adG]"]
    segs = [s for s in segmentos if s.get("arquivo")]
    if segs:
        linhas.append(f"[adial]asplit={1 + len(segs)}[adA]" + "".join(f"[adSC{i}]" for i in range(len(segs))))
    else:
        linhas.append("[adial]anull[adA]")
    linhas.append(f"[adA]volume={ganho_fala:.2f}dB[adG]")

    # ---- trilha (um ou mais trechos, com crossfade entre eles)
    # nas cartelas a trilha some (ou abaixa) e só o efeito de suspense toca; volta quando a cena seguinte aparece
    ganho_cartelas = ""
    for c in cenas[:-1]:
        K = c.get("cartela_depois")
        if not K or K.get("trilha") == "continua" or "cartela_ini" not in c:
            continue
        a_, b_ = c["cartela_ini"], c["cartela_ini"] + float(K["duracao"]) - float(K["fusao"])
        fd = float(K.get("trilha_fade", 0.4))
        piso = 10 ** (float(K.get("trilha_abaixa_db", -18)) / 20) if K.get("trilha") == "abaixa" else 0.0
        g = f"max(clip(({fmt(a_)}-t)/{fmt(fd)},0,1),clip((t-{fmt(b_)})/{fmt(fd)},0,1))"
        ganho_cartelas += f",volume='{piso:.4f}+{1 - piso:.4f}*{g}':eval=frame"
    trilha_info = []
    xf = float(TR.get("crossfade", 2.0))
    sequencial = TR.get("troca_fade_out") is not None and TR.get("troca_fade_in") is not None
    thr = 10 ** (float(TR["ducking_limiar_db"]) / 20)
    for i, seg in enumerate(segs):
        trilha = Path(seg["arquivo"])
        k = f"lufs:{trilha}"
        if k not in estado:
            estado[k] = medir_lufs(trilha)
        lt = estado[k] if estado[k] is not None else -20.0
        ganho_m = max(-40.0, min(20.0, TR["lufs"] - lt))
        ini = float(seg["inicio"])
        fim = float(segs[i + 1]["inicio"]) if i + 1 < len(segs) else total
        ultimo = i + 1 == len(segs)
        comp = max(0.5, fim - ini + (0 if ultimo or sequencial else xf))
        tdur = float(seg.get("duracao_trilha") or 0)
        off = float(seg.get("offset", 0.0))
        loop = ""
        if tdur > 0 and off + comp + 1 > tdur:
            if off >= tdur:
                off = off % tdur
            if off + comp + 1 > tdur:
                loop = f"aloop=loop=-1:size={int(tdur * 44100)},"
        fi = float(seg.get("fade_in") or (TR["fade_in"] if i == 0 else float(TR["troca_fade_in"]) if sequencial else xf))
        fo = float(TR["fade_out"]) if ultimo else (float(TR["troca_fade_out"]) if sequencial else xf)
        mi = add_input("-i", str(trilha))
        delay = f",adelay={int(round(ini * 1000))}|{int(round(ini * 1000))}" if ini > 0.001 else ""
        delay += ganho_cartelas
        linhas.append(f"[{mi}:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,{loop}"
                      f"atrim=start={fmt(off)}:end={fmt(off + comp)},asetpts=PTS-STARTPTS,volume={ganho_m:.2f}dB,"
                      f"afade=t=in:st=0:d={fmt(min(fi, comp / 2))},afade=t=out:st={fmt(max(0, comp - fo))}:d={fmt(min(fo, comp / 2))}"
                      f"{delay}[mus{i}]")
        linhas.append(f"[mus{i}][adSC{i}]sidechaincompress=threshold={thr:.5f}:ratio={TR['ducking_razao']}:attack=100:"
                      f"release=600:makeup=1:detection=rms[musd{i}]")
        mix_in.append(f"[musd{i}]")
        trilha_info.append({"arquivo": str(trilha), "inicio": round(ini, 2), "fim": round(fim, 2), "offset": round(off, 2),
                            "ganho_db": round(ganho_m, 1), "loop": bool(loop), "por_que": seg.get("por_que", "")})

    # ---- efeitos sonoros
    lista_sfx = []
    for idx, (tempo, arq, pico_alvo, dur_loop) in enumerate(eventos_sfx):
        # o volume é calculado pelo pico do trecho que toca (um efeito de 30 s cortado em 3 s não pode ser
        # nivelado pelo pico que só acontece aos 21 s)
        k = f"pico:{arq}" + (f":{dur_loop:.2f}" if dur_loop else "")
        if k not in estado:
            estado[k] = medir_pico_db(arq, dur_loop)
        pico = estado[k] if estado[k] is not None else -1.0
        ganho = max(-40.0, min(20.0, pico_alvo - pico))
        si = add_input("-i", str(arq))
        ms = int(round(tempo * 1000))
        cadeia = "aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,"
        if dur_loop:
            cadeia += f"aloop=loop=-1:size={int(44100 * 10)},atrim=0:{fmt(dur_loop)},afade=t=out:st={fmt(max(0, dur_loop - 0.25))}:d=0.25,"
        cadeia += f"volume={ganho:.2f}dB,adelay={ms}|{ms}"
        linhas.append(f"[{si}:a]{cadeia}[sfx{idx}]")
        mix_in.append(f"[sfx{idx}]")
        lista_sfx.append({"tempo": round(tempo, 2), "arquivo": arq.name, "pasta": arq.parent.name})
    if len(mix_in) > 1:
        linhas.append("".join(mix_in) + f"amix=inputs={len(mix_in)}:duration=first:normalize=0:dropout_transition=0,"
                      "alimiter=limit=0.95:attack=5:release=60[aout]")
    else:
        linhas.append("[adG]alimiter=limit=0.95:attack=5:release=60[aout]")

    script = trabalho / f"filtro_parte{num}.txt"
    script.write_text(";\n".join(linhas) + "\n", encoding="utf-8")
    saida.parent.mkdir(parents=True, exist_ok=True)
    args += ["-/filter_complex", str(script), "-map", "[vall]", "-map", "[aout]", "-t", fmt(total),
             "-r", str(F)] + codificador(cfg, trabalho) + ["-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                                                          "-movflags", "+faststart", str(saida)]
    nome = "Prévia" if num == 0 else f"Parte {num}"
    log(f"\nRenderizando {nome}: {len(cenas)} cenas, {conteudo:.1f}s de conteúdo, {total:.1f}s no total...")
    t0 = time.time()
    p = subprocess.run(args, cwd=str(trabalho), capture_output=True)
    if p.returncode != 0:
        log(p.stderr.decode("utf-8", "replace")[-6000:])
        raise RuntimeError(f"ffmpeg falhou na {nome} (filtro em {script})")
    log(f"   pronto em {time.time() - t0:.0f}s -> {saida}")
    mix = verificar_mix(saida, cenas, conteudo) if segs else None
    if mix:
        ok = mix["diferenca_db"] >= float(TR.get("diferenca_minima_db", 10))
        log(f"   conferência do áudio: fala {mix['fala_dbfs']} dBFS | fundo (trilha nos silêncios) {mix['fundo_dbfs']} dBFS | "
            f"diferença {mix['diferenca_db']} dB {'OK' if ok else 'ATENÇÃO: trilha alta demais'}")
    return {"arquivo": str(saida), "duracao": total, "conteudo": conteudo, "blocos_legenda": n_blocos,
            "pb_s": float(E["pb_duracao"]) if final_parte1 else 0.0,
            "cartelas_s": sum(float(c["cartela_depois"]["duracao"]) for c in cenas[:-1] if c.get("cartela_depois")),
            "ganho_fala_db": round(ganho_fala, 1), "lufs_fala_medido": round(lufs_fala, 1), "trilha": trilha_info,
            "efeitos": lista_sfx, "mix": mix}


# ----------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description="Edita Parte 1 e Parte 2 de uma história a partir das cenas numeradas.")
    ap.add_argument("pasta", help="pasta da história (com os clipes ou com a subpasta 'cenas')")
    ap.add_argument("--briefing", help="arquivo de briefing (padrão: briefing.txt na pasta)")
    ap.add_argument("--estilo", help="estilo da trilha: drama, suspense, ação, inspiradora, piano, normal...")
    ap.add_argument("--parte", type=int, choices=[1, 2], help="renderizar só uma parte")
    ap.add_argument("--so-planejar", action="store_true", help="mostra o plano e não renderiza")
    ap.add_argument("--forcar-transcricao", action="store_true", help="ignora o cache de transcrições")
    ap.add_argument("--modelo-local", default="small", help="modelo faster-whisper se não houver Groq (small, large-v3-turbo)")
    ap.add_argument("--saida", help="pasta de saída (padrão: <pasta>/PRONTO)")
    ap.add_argument("--previa-de", type=int, metavar="CENA",
                    help="a prévia começa no fim desta cena (ex.: 2 = fim da cena 2 + cartela + começo da cena 3)")
    ap.add_argument("--previa-cauda", type=float, default=5.0, metavar="SEGUNDOS",
                    help="com --previa-de: quantos segundos do fim da primeira cena entram (padrão 5)")
    ap.add_argument("--previa", type=float, nargs="?", const=15.0, metavar="SEGUNDOS",
                    help="renderiza só uma prévia do início da Parte 1 (padrão 15 s) em PRONTO/Previa.mp4")
    a = ap.parse_args()

    cfg = carregar_cfg()
    pasta = Path(a.pasta).expanduser().resolve()
    if not pasta.is_dir():
        erro(f"pasta não encontrada: {pasta}")
    trabalho = pasta / "trabalho"
    trabalho.mkdir(exist_ok=True)
    saida = Path(a.saida).resolve() if a.saida else pasta / "PRONTO"

    brief_path = Path(a.briefing) if a.briefing else pasta / "briefing.txt"
    brief = {"cenas": {}}
    if brief_path.exists():
        log(f"Briefing: {brief_path}")
        brief = parse_briefing(brief_path.read_text(encoding="utf-8", errors="replace"))
    maiusculas = brief.get("legenda_maiusculas", cfg["legenda"]["maiusculas"])
    if "cor" in brief:
        cfg.setdefault("cor", {})["ativa"] = brief["cor"]

    cenas = planejar(pasta, trabalho, cfg, brief, a.forcar_transcricao, a.modelo_local)
    k = dividir(cenas, cfg, brief)
    p1, p2 = cenas[:k], cenas[k:]
    d1, d2 = sum(c["dur_final"] for c in p1), sum(c["dur_final"] for c in p2)
    log(f"\nDivisão: Parte 1 = cenas {p1[0]['n']}–{p1[-1]['n']} ({d1:.1f}s de cenas) | "
        + (f"Parte 2 = cenas {p2[0]['n']}–{p2[-1]['n']} ({d2:.1f}s)" if p2 else "sem Parte 2"))

    estado_path = trabalho / "medicoes.json"
    estado = json.loads(estado_path.read_text(encoding="utf-8")) if estado_path.exists() else {}
    duracoes = estado.setdefault("duracoes", {})
    E = dict(cfg["encerramento"])
    E.update(brief.get("encerramento", {}))
    continua = bool(brief.get("continua", cfg["encerramento"].get("continua", True)))
    enc_dur = (E["pb_duracao"] + (E.get("cartao_dur") or (E["inicio_digitacao"] + len(E["texto"]) / E["letras_por_segundo"]
                                                          + E["segurar"] + E["fade_final"]))) if continua else 0.0
    log("Encerramento: " + ("flash -> P&B -> “" + E["texto"] + "” (pedido no briefing)" if continua
                            else "fade para o preto (o “Continua no Próximo episódio...” só entra com 'continua: sim')"))

    # ---- clima da história e escolha da trilha
    log("\nCatálogo de trilhas (mede/descreve só o que for novo)...")
    cat = trilhas.catalogar(Path(cfg["trilha"]["pasta"]), usar_gemini=True, gemini_so_novos=True, log=lambda m: log("   " + m))
    clima1 = trilhas.clima_das_falas([c["texto"] for c in p1])
    clima2 = trilhas.clima_das_falas([c["texto"] for c in p2]) if p2 else clima1
    for nome, cl in (("Parte 1", clima1), ("Parte 2", clima2))[: 2 if p2 else 1]:
        achados = "; ".join(f"{c}: {', '.join(v)}" for c, v in cl["achados"].items() if v)
        log(f"Clima {nome}: " + ", ".join(f"{c} {cl['notas'][c]:.1f}" for c in trilhas.CLIMAS)
            + f" | intensidade {cl['intensidade']:.2f} | dominante: {cl['dominante']}")
        if achados:
            log(f"   palavras: {achados}")
    continuar = cfg["trilha"].get("continuar_na_parte2", True)
    nec1, nec2 = d1 + enc_dur + 2, d2 + 2
    if brief.get("trilha"):
        t1, pq1 = resolver_trilha(cat, brief["trilha"], clima1, nec1 + nec2)
        t2, pq2 = t1, "mesma trilha (briefing)"
    else:
        if brief.get("trilha_parte1"):
            t1, pq1 = resolver_trilha(cat, brief["trilha_parte1"], clima1, nec1)
        else:
            t1, pq1 = trilhas.escolher_por_clima(cat, clima1, nec1 + (nec2 if continuar else 0), a.estilo)
        if brief.get("trilha_parte2"):
            t2, pq2 = resolver_trilha(cat, brief["trilha_parte2"], clima2, nec2)
        elif p2:
            t2, pq2 = trilhas.escolher_por_clima(cat, clima2, nec2, a.estilo)
        else:
            t2, pq2 = t1, ""
    if t1 is None and cat.get("trilhas") == {}:
        t1 = escolher_trilha(cfg, brief, a.estilo, nec1 + nec2, pasta.name, duracoes)
        t2, pq1, pq2 = t1, "catálogo vazio: escolha pela pasta do estilo", ""

    def dur_trilha(p: Path | None) -> float:
        if not p:
            return 0.0
        if str(p) not in duracoes:
            duracoes[str(p)] = probe(p)["dur"]
        return duracoes[str(p)]

    TRc = cfg["trilha"]
    # com troca em fade (sem crossfade) a trilha nova entra junto com a cena; no crossfade, 0,9 s antes da transição
    troca_antes = 0.0 if TRc.get("troca_fade_out") is not None else float(TRc.get("troca_antes_da_transicao", 0.9))
    AB = TRc.get("abertura", {})

    def abertura(cenas_parte: list[dict], num: int, principal: Path | None, manual: bool) -> tuple[Path | None, float, str]:
        """Trilha tensa do gancho (como nos exemplos) e a cena em que a trilha da história entra."""
        pedido = brief.get("trilha_abertura", "")
        if pedido is None or not AB.get("ativa", True) or (manual and not pedido) or len(cenas_parte) < 2:
            return None, 0.0, ""
        calcular_offsets(cenas_parte, cfg)
        lo, hi = AB.get(f"parte{num}_troca_entre_s", [15, 32] if num == 1 else [6, 17])
        cands = [c for c in cenas_parte[1:] if lo <= c["offset"] <= hi]
        if not cands:
            return None, 0.0, ""

        def emocional(c: dict) -> bool:
            n = (c.get("clima") or {}).get("notas", {})
            return n.get("tristeza", 0) + n.get("esperanca", 0) > n.get("tensao", 0) + n.get("acao", 0)
        alvo = next((c for c in cands if emocional(c)), min(cands, key=lambda c: abs(c["offset"] - (lo + hi) / 2)))
        antes = cenas_parte[: cenas_parte.index(alvo)]
        cl = trilhas.clima_das_falas([c["texto"] for c in antes])
        necessario = alvo["offset"] + 2
        if pedido:
            p, pq = resolver_trilha(cat, pedido, cl, necessario)
        else:
            pasta = "Suspense" if cl["notas"]["tensao"] > cl["notas"]["acao"] else "Epic"
            p, pq = trilhas.escolher_por_clima(cat, cl, necessario, pasta_forcada=pasta)
        if not p or (principal and str(p) == str(principal)):
            return None, 0.0, ""
        return p, alvo["offset"], f"abertura até a cena {alvo['n'] - 1} (gancho): {pq}"

    def segmentos_da_parte(cenas_parte: list[dict], base: Path | None, offset_base: float, por_que: str, clima: dict,
                           num: int, manual: bool) -> list[dict]:
        ab, t_troca, pq_ab = abertura(cenas_parte, num, base, manual)
        segs = []
        if ab:
            segs.append({"inicio": 0.0, "arquivo": ab, "offset": 0.0, "duracao_trilha": dur_trilha(ab), "por_que": pq_ab})
        if base:
            ini = max(0.0, t_troca - troca_antes) if ab else 0.0
            segs.append({"inicio": round(ini, 3), "arquivo": base, "offset": 0.0 if ab else offset_base,
                         "duracao_trilha": dur_trilha(base), "por_que": por_que})
        total = calcular_offsets(cenas_parte, cfg)
        for jc, c in enumerate(cenas_parte):
            if c.get("trilha_pedida"):
                tp, pq = resolver_trilha(cat, c["trilha_pedida"], trilhas.clima_das_falas([c["texto"]]), total - c["offset"])
                if tp:
                    K = cenas_parte[jc - 1].get("cartela_depois") if jc > 0 else None
                    # depois da cartela a música nova entra junto com a cena (do início dela); senão, 0,9 s antes
                    ini = c["offset"] if K else max(0.0, c["offset"] - troca_antes)
                    segs = [s for s in segs if s["inicio"] < ini]
                    segs.append({"inicio": round(ini, 3), "arquivo": tp, "offset": 0.0, "duracao_trilha": dur_trilha(tp),
                                 "por_que": f"cena {c['n']}: {pq}" + (" (entra com a cena, depois da cartela)" if K else ""),
                                 **({"fade_in": float(K["fusao"])} if K else {})})
        return segs

    off2 = d1 if (continuar and t1 and t2 and str(t1) == str(t2)) else 0.0
    manual1 = bool(brief.get("trilha") or brief.get("trilha_parte1"))
    manual2 = bool(brief.get("trilha") or brief.get("trilha_parte2"))
    segs1 = segmentos_da_parte(p1, t1, 0.0, pq1, clima1, 1, manual1)
    segs2 = segmentos_da_parte(p2, t2, off2, pq2, clima2, 2, manual2) if p2 else []
    for nome, segs in (("Parte 1", segs1), ("Parte 2", segs2 if p2 else None)):
        if segs is None:
            continue
        if not segs:
            log(f"Trilha {nome}: nenhuma")
        for i, s in enumerate(segs):
            quando = "desde o início" if i == 0 else f"entra em {s['inicio']:.1f}s"
            cont = " (continua de onde a Parte 1 parou)" if s.get("offset") else ""
            log(f"Trilha {nome} {quando}{cont}: {s['por_que']}")
    log("Transições: " + ", ".join(f"{c['n']}→{c['transicao']}" + (f" ({c['motivo_transicao']})" if c.get("motivo_transicao") else "")
                                   for c in cenas[:-1] if c["transicao"] in ("dissolve", "leak") or c.get("motivo_transicao")))
    log("Câmera: " + ("; ".join(f"cena {c['n']} {c['motivo_camera'].strip()}" for c in cenas if c.get("motivo_camera"))
                      or "só o recorte base") + f" | base {cfg.get('camera', {}).get('zoom_base', 1.0)}"
        + (f" | cor: {'ligada' if (cfg.get('cor') or {}).get('ativa') else 'desligada'}"))
    folha = folha_cenas_brutas(cenas, trabalho)
    if folha:
        log(f"Folha das cenas originais (procure texto/legenda/marca gravados na imagem): {folha}")
    grade = grade_cenas(cenas, trabalho, cfg)
    if grade:
        log(f"Grade das cenas (posição dos rostos para 'zoom in no rosto X Y'): {grade}")

    # ---- sugestões de efeitos pelas falas
    sugestoes = trilhas.sugerir_efeitos([c["texto"] for c in cenas], Path(cfg["efeitos"]["pasta"]))
    if sugestoes:
        aplicar = bool(cfg["efeitos"].get("aplicar_sugestoes", False))
        log("Efeitos sugeridos pelas falas" + (" (APLICADOS)" if aplicar else " (não aplicados; coloque no briefing se fizer sentido)") + ":")
        for s in sugestoes:
            alvo = cenas[s["cena"] - 1]
            s["cena"] = alvo["n"]
            log(f"   cena {s['cena']}: {s['efeito']}  (palavra '{s['palavra']}')")
            if aplicar and not alvo["efeitos"]:
                alvo["efeitos"].append({"nome": s["efeito"], "em": 0.0, "volume": 0.0})

    plano = {"pasta": str(pasta), "divisao": k, "legenda_maiusculas": maiusculas,
             "clima": {"parte1": clima1, "parte2": clima2},
             "trilha": {"parte1": [{kk: (str(v) if isinstance(v, Path) else v) for kk, v in s.items()} for s in segs1],
                        "parte2": [{kk: (str(v) if isinstance(v, Path) else v) for kk, v in s.items()} for s in segs2]},
             "efeitos_sugeridos": sugestoes,
             "cenas": [{kk: (str(v) if isinstance(v, Path) else v) for kk, v in c.items() if kk != "palavras"} for c in cenas]}
    (trabalho / "plano.json").write_text(json.dumps(plano, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.so_planejar:
        log("\n(só planejar) plano salvo em " + str(trabalho / "plano.json"))
        return

    if a.previa:
        # prévia: começo da Parte 1 com o mesmo estilo (legendas, transições, woosh, trilha com ducking), sem encerramento.
        # Pelo menos 2 cenas para mostrar uma transição; a última é aparada se passar muito do alvo.
        # Com --previa-de N a prévia começa nos últimos segundos da cena N (ex.: fim da cena 2 + cartela + cena 3).
        alvo = float(a.previa)
        idx = next((i for i, c in enumerate(cenas) if c["n"] >= a.previa_de), 0) if a.previa_de else 0
        parte, segs_parte = (p1, segs1) if idx < k else (p2, segs2)
        calcular_offsets(parte, cfg)
        fonte = [dict(c, camera=dict(c["camera"])) for c in cenas[idx: (k if idx < k else len(cenas))]]
        inicio_na_parte = fonte[0]["offset"]
        if a.previa_de:
            u = fonte[0]
            manter = min(u["dur_final"], max(2.0, float(a.previa_cauda)))
            delta = round(u["dur_final"] - manter, 3)
            if delta > 0:
                u["inicio"] = round(u["inicio"] + delta, 3)
                u["dur_final"] = round(manter, 3)
                # câmera em tempo da cena: desloca para continuar igual ao vídeo completo
                u["camera"]["zoom"] = [(t - delta, z) for t, z in u["camera"].get("zoom") or []]
                if u["camera"].get("enquadrar"):
                    u["camera"]["enquadrar"] = [(t - delta, x) for t, x in u["camera"]["enquadrar"]]
                inicio_na_parte += delta
        cp, acum = [], 0.0
        for c in fonte:
            if acum >= alvo - 1.5 and len(cp) >= 2:
                break
            cp.append(c)
            acum += c["dur_final"]
            if c.get("cartela_depois"):
                acum += float(c["cartela_depois"]["duracao"]) - float(c["cartela_depois"]["fusao"])
        if acum > alvo + 3 and len(cp) >= 2:
            u = cp[-1]
            u["fim"] = round(max(u["inicio"] + cfg["cortes"]["minimo_cena"], u["fim"] - (acum - alvo)), 3)
            u["dur_final"] = round(u["fim"] - u["inicio"], 3)
            u["palavras"] = [w for w in u["palavras"] if w["s"] < u["fim"]]
        dur_p = calcular_offsets(cp, cfg)
        # a mesma música do vídeo completo naquele trecho: o trecho que já tocava + as trocas que caem na prévia
        segs_p = []
        atual = [s_ for s_ in segs_parte if s_["inicio"] <= inicio_na_parte + 1e-3]
        if atual:
            s0 = dict(atual[-1])
            s0["offset"] = float(s0.get("offset", 0.0)) + (inicio_na_parte - float(s0["inicio"]))
            s0["inicio"] = 0.0
            s0.pop("fade_in", None)
            segs_p.append(s0)
        for s_ in segs_parte:
            if inicio_na_parte + 1e-3 < s_["inicio"] < inicio_na_parte + dur_p:
                segs_p.append(dict(s_, inicio=round(s_["inicio"] - inicio_na_parte, 3)))
        try:
            r = render_parte(0, cp, cfg, brief, trabalho, saida / "Previa.mp4", segs_p, False, maiusculas, estado)
        finally:
            estado_path.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
        log(f"\nPrévia: cenas {cp[0]['n']}–{cp[-1]['n']}, {r['duracao']:.1f}s -> {r['arquivo']}")
        return

    resultados = {}
    try:
        if a.parte in (None, 1):
            resultados[1] = render_parte(1, p1, cfg, brief, trabalho, saida / "Parte 1.mp4", segs1, continua, maiusculas, estado)
        if a.parte in (None, 2) and p2:
            resultados[2] = render_parte(2, p2, cfg, brief, trabalho, saida / "Parte 2.mp4", segs2, False, maiusculas, estado)
    finally:
        estado_path.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")

    # ---- checklist das Políticas de Monetização de Conteúdo (CMP) em cada parte pronta
    log("\nChecklist de monetização (CMP)...")
    for num, r in resultados.items():
        try:
            calcular_offsets(p1 if num == 1 else p2, cfg)
            res = monetizacao.verificar_parte(num, p1 if num == 1 else p2, Path(r["arquivo"]), cfg, trabalho, r)
            ruins = [i for i in res["itens"] if i["status"] in (monetizacao.BLOQUEIA, monetizacao.ATENCAO)]
            for i in ruins:
                log(f"   Parte {num} {i['status']} {i['item']}: {i['evidencia']}" + (f" -> {i['correcao']}" if i["correcao"] else ""))
        except Exception as e:  # noqa — o checklist nunca derruba a edição
            log(f"   Parte {num}: checklist falhou ({e})")
    arq_cl, n_bloq, n_pend = monetizacao.escrever(pasta)
    log(f"   {arq_cl}: ❌ {n_bloq}, 👁 {n_pend} (revisão visual: trabalho\\folha_parteN.png e cantos_parteN.png)")

    # relatório
    rel = [f"# Relatório da edição — {pasta.name}", "",
           (f"- Legendas: {'MAIÚSCULAS' if maiusculas else 'minúsculas'}, {cfg['legenda']['fonte']}"
            if brief.get("legendas", cfg["legenda"].get("ativa", True)) else "- Legendas: desligadas"),
           f"- Divisão: Parte 1 = cenas {p1[0]['n']}–{p1[-1]['n']}"
           + (f"; Parte 2 = cenas {p2[0]['n']}–{p2[-1]['n']}" if p2 else ""),
           f"- Câmera: base {cfg.get('camera', {}).get('zoom_base', 1.0)}; cor {'ligada' if (cfg.get('cor') or {}).get('ativa') else 'desligada'}",
           "- Monetização: ver checklist_monetizacao.md", ""]
    for nome, cl in (("Parte 1", clima1), ("Parte 2", clima2)):
        rel.append(f"- Clima {nome}: " + ", ".join(f"{c} {cl['notas'][c]:.1f}" for c in trilhas.CLIMAS)
                   + f"; intensidade {cl['intensidade']:.2f}; dominante {cl['dominante']}")
    if sugestoes:
        rel.append("- Efeitos sugeridos pelas falas: " + "; ".join(f"cena {s['cena']} → {s['efeito']} ('{s['palavra']}')" for s in sugestoes))
    rel.append("")
    for num, r in resultados.items():
        rel.append(f"## Parte {num} — {r['duracao']:.1f}s ({r['conteudo']:.1f}s de cenas)")
        rel.append(f"- arquivo: {r['arquivo']}")
        rel.append(f"- fala medida {r['lufs_fala_medido']} LUFS, ganho {r['ganho_fala_db']} dB; blocos de legenda: {r['blocos_legenda']}")
        if r.get("mix"):
            rel.append(f"- conferência: fala {r['mix']['fala_dbfs']} dBFS, fundo {r['mix']['fundo_dbfs']} dBFS, "
                       f"diferença {r['mix']['diferenca_db']} dB")
        for t in r["trilha"]:
            rel.append(f"- trilha {t['inicio']}–{t['fim']}s: {Path(t['arquivo']).parent.name} / {Path(t['arquivo']).name} "
                       f"(a partir de {t['offset']}s da música, ganho {t['ganho_db']} dB{', em loop' if t['loop'] else ''})")
            if t.get("por_que"):
                rel.append(f"  - por quê: {t['por_que']}")
        for e in r["efeitos"]:
            rel.append(f"- efeito {e['tempo']}s: {e['pasta']} / {e['arquivo']}")
        rel.append("")
    rel.append("## Cenas")
    rel.append("| # | arquivo | original | usado | transição | câmera | fala |")
    rel.append("|---|---|---|---|---|---|---|")
    for c in cenas:
        rel.append(f"| {c['n']} | {c['arquivo'].name} | {c['dur_orig']:.1f}s | {c['inicio']:.2f}–{c['fim']:.2f} "
                   f"({c['dur_final']:.1f}s) | {c['transicao']} | {c.get('motivo_camera', '').strip() or '-'} | {c['texto'][:90]} |")
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "relatorio.md").write_text("\n".join(rel) + "\n", encoding="utf-8")
    log(f"\nRelatório: {saida / 'relatorio.md'}")


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa
            pass
    try:
        main()
    except KeyboardInterrupt:
        erro("interrompido")
