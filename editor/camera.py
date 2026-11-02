# -*- coding: utf-8 -*-
r"""
camera.py — Movimentos de câmera, enquadramento 9:16 e cor, como nos vídeos de exemplo 2 e 3.

Medido em 27/10/2026 comparando cada clipe ORIGINAL (achados em Downloads pelo áudio) com o vídeo editado:
- zoom in lento e LINEAR na cena inteira: 1,00 -> 1,14 e 1,00 -> 1,09 (falas tristes/confissão);
- zoom out lento e linear saindo do rosto: 1,22 -> 1,00 e ~1,35 -> 1,00 (alívio, pergunta, revelação);
- zoom de impacto no gancho (3 pt 1): sobe devagar, aperta até 1,32 em ~2,5 s na exclamação
  ("Moço, pelo amor de Deus!"), segura 0,25 s e volta em ~3 s; o zoom mira o rosto (x 0,75 do quadro);
- recorte fixo: base ~1,02; 1,13 quando o clipe veio com texto gravado (legenda da IA) para tirá-lo da imagem;
- clipes horizontais (história 2): recorte 9:16 parado ou deslizando devagar e linear (keyframes) e, num caso,
  imagem espelhada. Centralizar erra menos (0,049 da largura) que rastrear por pele/movimento (0,06–0,10):
  o padrão é o centro e o diretor define "enquadrar 0.3 > 0.41"; rastrear() fica para "enquadrar seguir";
- cor (2 pt 2, 3 pt 1, 3 pt 2): mais contraste e sombras mais fundas, leve tom frio, cores um pouco mais vivas e
  vinheta leve; os valores do config.json foram ajustados renderizando os clipes originais da história 3
  (editor	este_h3) até a diferença para a edição do usuário ficar < 1%.
"""
from __future__ import annotations

import subprocess

try:
    import numpy as np
except ImportError:  # sem numpy: sem medições automáticas (o resto funciona)
    np = None


def fmt(t: float) -> str:
    return f"{t:.3f}"


# ----------------------------------------------------------------------------- leitura de quadros
def quadros(path, t0: float, dur: float, w: int, h: int, fps: float, pix: str = "gray"):
    ch = 3 if pix == "rgb24" else 1
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", fmt(t0), "-t", fmt(dur), "-i", str(path),
                          "-vf", f"fps={fps},scale={w}:{h}:flags=area", "-f", "rawvideo", "-pix_fmt", pix, "-"],
                         capture_output=True).stdout
    n = len(raw) // (w * h * ch)
    a = np.frombuffer(raw[: n * w * h * ch], np.uint8).astype(np.float32)
    return a.reshape(n, h, w, ch) if ch == 3 else a.reshape(n, h, w)


def _resize(img, f: float):
    h, w = img.shape
    nh, nw = max(2, int(round(h * f))), max(2, int(round(w * f)))
    ys = (np.arange(nh) + 0.5) / f - 0.5
    xs = (np.arange(nw) + 0.5) / f - 0.5
    y0 = np.clip(np.floor(ys).astype(int), 0, h - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, w - 1)
    y1, x1 = np.clip(y0 + 1, 0, h - 1), np.clip(x0 + 1, 0, w - 1)
    wy = np.clip(ys - y0, 0, 1)[:, None]
    wx = np.clip(xs - x0, 0, 1)[None, :]
    return (img[y0][:, x0] * (1 - wx) + img[y0][:, x1] * wx) * (1 - wy) + (img[y1][:, x0] * (1 - wx) + img[y1][:, x1] * wx) * wy


def _passa_alta(x, k: int = 6):
    c = np.cumsum(np.cumsum(np.pad(x, ((k, k), (k, k)), mode="edge"), 0), 1)
    s = (c[2 * k:, 2 * k:] - c[:-2 * k, 2 * k:] - c[2 * k:, :-2 * k] + c[:-2 * k, :-2 * k]) / (4 * k * k)
    return x - s[: x.shape[0], : x.shape[1]]


def _ncc(img, tpl):
    """correlação normalizada de tpl dentro de img (FFT); devolve (pico, y, x)."""
    H, W = img.shape
    h, w = tpl.shape
    if H < h or W < w:
        return -1.0, 0, 0
    t = tpl - tpl.mean()
    tn = np.sqrt((t * t).sum()) + 1e-6
    num = np.fft.irfft2(np.fft.rfft2(img, (H, W)) * np.conj(np.fft.rfft2(t, (H, W))), (H, W))[: H - h + 1, : W - w + 1]
    c1 = np.pad(np.cumsum(np.cumsum(img, 0), 1), ((1, 0), (1, 0)))
    c2 = np.pad(np.cumsum(np.cumsum(img * img, 0), 1), ((1, 0), (1, 0)))

    def box(c):
        return c[h:, w:] - c[:-h, w:] - c[h:, :-w] + c[:-h, :-w]
    var = np.maximum(box(c2) - box(c1) ** 2 / (h * w), 1e-6)
    r = num / (np.sqrt(var) * tn)
    i = np.unravel_index(int(np.argmax(r)), r.shape)
    return float(r[i]), int(i[0]), int(i[1])


# ----------------------------------------------------------------------------- medições no clipe original
def medir_camera(path, t0: float, t1: float, w: int, h: int) -> dict | None:
    """A câmera do próprio clipe já se move? Compara o começo e o fim do trecho usado e devolve a escala
    (>1 = a câmera aproximou) e o deslocamento horizontal (fração da largura)."""
    if np is None or t1 - t0 < 1.0:
        return None
    lw = 90 if w <= h else 160
    lh = int(round(lw * h / w / 2)) * 2
    try:
        A = quadros(path, t0 + 0.15, 0.2, lw, lh, 5)
        B = quadros(path, max(t0 + 0.4, t1 - 0.35), 0.2, lw, lh, 5)
    except Exception:  # noqa
        return None
    if not len(A) or not len(B):
        return None
    A, B = _passa_alta(A[0]), _passa_alta(B[0])
    m = int(lw * 0.08)
    melhor = (-2.0, 1.0, 0.0)
    for s in np.geomspace(1.0, 1.3, 16):
        for img, tpl, sinal in ((A, B, 1), (B, A, -1)):
            big = _resize(img, s)
            t_ = tpl[m:-m, m:-m]
            sc, y, x = _ncc(big, t_)
            if sc > melhor[0]:
                cx = (x + t_.shape[1] / 2) / big.shape[1]
                melhor = (sc, s ** sinal, (cx - 0.5) * sinal)
    sc, esc, dx = melhor
    return {"escala": round(float(esc), 3), "desloc": round(float(dx), 3), "confianca": round(sc, 2),
            "parada": bool(sc > 0.35 and abs(np.log(esc)) < 0.045 and abs(dx) < 0.04)}


def _pele(rgb):
    """máscara de pele (YCbCr) — serve para achar rostos/pessoas sem bibliotecas extras."""
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b
    return ((cr > 135) & (cr < 180) & (cb > 80) & (cb < 135) & (y > 35)).astype(np.float32)


def centro_rosto(path, t: float, w: int, h: int) -> tuple[float, float] | None:
    """Ponto para onde o zoom mira (como nos exemplos, o rosto). None se não achar."""
    if np is None:
        return None
    lw = 96
    lh = int(round(lw * h / w))
    try:
        f = quadros(path, max(0.0, t), 0.2, lw, lh, 5, "rgb24")
    except Exception:  # noqa
        return None
    if not len(f):
        return None
    p = _pele(f[0])
    p[int(lh * 0.8):] *= 0.3            # rostos ficam no alto; mãos/braços embaixo pesam menos
    k = max(3, lw // 8)
    c = np.cumsum(np.cumsum(np.pad(p, ((k, k), (k, k))), 0), 1)
    dens = (c[2 * k:, 2 * k:] - c[:-2 * k, 2 * k:] - c[2 * k:, :-2 * k] + c[:-2 * k, :-2 * k]) / (4 * k * k)
    if dens.max() < 0.25:
        return None
    y, x = np.unravel_index(int(np.argmax(dens)), dens.shape)
    return round(float((x + 0.5) / lw), 3), round(float((y + 0.5) / lh), 3)


def rostos(path, t: float, w: int, h: int, maximo: int = 3) -> list[tuple[float, float, float]]:
    """Rostos/pessoas visíveis no quadro (manchas de pele no alto), da esquerda para a direita: [(x, y, força)].
    Serve para o "zoom in no rosto do personagem": o diretor diz qual (esquerda/direita/centro) olhando a folha."""
    if np is None:
        return []
    lw = 120
    lh = int(round(lw * h / w))
    try:
        f = quadros(path, max(0.0, t), 0.2, lw, lh, 5, "rgb24")
    except Exception:  # noqa
        return []
    if not len(f):
        return []
    p = _pele(f[0])
    p[int(lh * 0.8):] *= 0.3
    k = max(3, lw // 10)
    c = np.cumsum(np.cumsum(np.pad(p, ((k, k), (k, k))), 0), 1)
    dens = (c[2 * k:, 2 * k:] - c[:-2 * k, 2 * k:] - c[2 * k:, :-2 * k] + c[:-2 * k, :-2 * k]) / (4 * k * k)
    achados = []
    d = dens.copy()
    raio = max(4, lw // 5)
    for _ in range(maximo):
        y, x = np.unravel_index(int(np.argmax(d)), d.shape)
        v = float(d[y, x])
        if v < 0.22 or (achados and v < 0.45 * achados[0][2]):
            break
        achados.append((round(float((x + 0.5) / lw), 3), round(float((y + 0.5) / lh), 3), round(v, 3)))
        d[max(0, y - raio): y + raio, max(0, x - raio): x + raio] = 0
    return sorted(achados, key=lambda r: r[0])


def rastrear(path, t0: float, t1: float, w: int, h: int, W: int, H: int, vel_max: float = 0.12) -> list[tuple[float, float]]:
    """Clipe horizontal num vídeo vertical: centro do recorte 9:16 ao longo do tempo seguindo a pessoa (pele +
    movimento), suavizado e com velocidade limitada como nos exemplos. Devolve [(t, cx 0..1)] em tempo do trecho."""
    if np is None:
        return [(0.0, 0.5)]
    lw = 192
    lh = int(round(lw * h / w))
    fps = 4
    try:
        F = quadros(path, t0, t1 - t0, lw, lh, fps, "rgb24")
    except Exception:  # noqa
        return [(0.0, 0.5)]
    if len(F) < 2:
        return [(0.0, 0.5)]
    janela = (h * W / H) / w                      # largura do recorte 9:16 em fração da largura
    jw = max(2, int(round(janela * lw)))
    cinza = F.mean(3)
    alvo = []
    for i in range(len(F)):
        p = _pele(F[i])[: int(lh * 0.75)]
        mov = np.abs(cinza[i] - cinza[max(0, i - 1)])[: int(lh * 0.75)] / 20.0
        perfil = (p * (1 + np.minimum(mov, 2))).sum(0) + 0.02 * lh
        perfil *= 1 - 0.15 * np.abs(np.linspace(-1, 1, lw))   # leve preferência pelo centro
        s = np.convolve(perfil, np.ones(jw), mode="valid")
        alvo.append((int(np.argmax(s)) + jw / 2) / lw)
    alvo = np.array(alvo)
    # mediana de 1 s e zona morta: só move quando a pessoa sai mesmo do lugar
    med = np.array([np.median(alvo[max(0, i - 2): i + 3]) for i in range(len(alvo))])
    lim = (janela / 2, 1 - janela / 2)
    pos = [float(np.clip(med[0], *lim))]
    passo = vel_max / fps
    for v in med[1:]:
        d = float(np.clip(v, *lim)) - pos[-1]
        if abs(d) < 0.04:
            d = 0.0
        pos.append(pos[-1] + float(np.clip(d, -passo, passo)))
    pts = [(round(i / fps, 2), round(x, 4)) for i, x in enumerate(pos)]
    # simplifica: só os pontos onde a direção muda
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1][1], pts[i][1], pts[i + 1][1]
        if (b - a) * (c - b) <= 0 and (b != a or c != b):
            out.append(pts[i])
    out.append(pts[-1])
    return out


# ----------------------------------------------------------------------------- expressões e filtro
def curva(keys: list[tuple[float, float]], T: str, suave: bool = False) -> str:
    """Expressão ffmpeg (por quadro) que passa pelos pontos (t, valor): linear como nos exemplos, ou suave."""
    if not keys:
        return "1"
    keys = sorted(keys)
    expr = f"{keys[-1][1]:.5f}"
    for (ta, va), (tb, vb) in reversed(list(zip(keys[:-1], keys[1:]))):
        if tb - ta < 1e-3:
            continue
        u = f"clip(({T}-{ta:.3f})/{tb - ta:.3f},0,1)"
        e = f"({u})*({u})*(3-2*({u}))" if suave else u
        expr = f"if(lt({T},{tb:.3f}),{va:.5f}+({vb - va:.5f})*{e},{expr})"
    return f"if(lt({T},{keys[0][0]:.3f}),{keys[0][1]:.5f},{expr})"


def filtro_cor(cfg: dict) -> str:
    C = cfg.get("cor") or {}
    if not C.get("ativa", False):
        return ""
    y = f"clip(val*{C.get('y_ganho', 1.0)}+({C.get('y_offset', 0.0)}),16,235)"
    u = f"clip((val-128)*{C.get('u_ganho', 1.0)}+128+({C.get('u_desvio', 0.0)}),16,240)"
    v = f"clip((val-128)*{C.get('v_ganho', 1.0)}+128+({C.get('v_desvio', 0.0)}),16,240)"
    s = f"lutyuv=y='{y}':u='{u}':v='{v}'"
    if C.get("vinheta", 0) > 0:
        s += f",vignette=angle={C['vinheta']}"
    return s


def filtro_camera(c: dict, cfg: dict, fixo_em: float | None = None) -> str:
    """Cadeia de vídeo de uma cena: espelhar -> preencher 9:16 (recorte que segue a pessoa nos clipes horizontais)
    -> zoom base -> movimento (perspective por quadro, suave) -> cor. fixo_em = tempo da cena em que o
    movimento congela (usado no P&B do encerramento, que continua do ponto em que a cena parou)."""
    V = cfg["video"]
    W, H, F = V["largura"], V["altura"], V["fps"]
    cam = c.get("camera") or {}
    w, h = int(c.get("w") or W), int(c.get("h") or H)
    zb = float(cam.get("zoom_base", 1.0))
    # os valores YUV do clipe passam direto, marcados como BT.709 (como o editor do usuário fez nos exemplos);
    # sem isso o ffmpeg converte BT.601 -> BT.709 e a imagem perde ~10% de cor e contraste
    partes = ["setpts=PTS-STARTPTS", "setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709"]
    if cam.get("espelhar"):
        partes.append("hflip")
    s = max(W / w, H / h) * zb
    sw, sh = int(round(w * s / 2)) * 2, int(round(h * s / 2)) * 2
    sw, sh = max(sw, W), max(sh, H)
    partes.append(f"scale={sw}:{sh}:flags=lanczos")
    trilho = cam.get("enquadrar") or [(0.0, 0.5)]
    if fixo_em is not None:
        trilho = [(0.0, valor_em(trilho, fixo_em))]
    cy = float(cam.get("centro_y", 0.5))
    y0 = max(0, min(sh - H, int(round(cy * sh - H / 2))))
    if len(trilho) > 1 and sw > W:
        xs = [(t, x * sw - W / 2) for t, x in trilho]
        partes.append(f"crop={W}:{H}:x='clip({curva(xs, 't')},0,{sw - W})':y={y0}")
    else:
        x0 = max(0, min(sw - W, int(round(trilho[0][1] * sw - W / 2))))
        partes.append(f"crop={W}:{H}:{x0}:{y0}")
    partes.append(f"setsar=1,fps={F}")
    zk = cam.get("zoom") or []
    if fixo_em is not None and zk:
        zk = [(0.0, valor_em(zk, fixo_em))]
    if zk and not (len(zk) == 1 and abs(zk[0][1] - 1.0) < 1e-3):
        T = f"(in/{F})"
        Z = f"({curva(zk, T)})"
        px, py = cam.get("mira", (0.5, 0.45))
        # janela de W/Z x H/Z que se aproxima do ponto (px, py) mantendo-o parado na tela
        x0 = f"clip({px:.4f}*W*(1-1/{Z}),0,W-W/{Z})"
        y0e = f"clip({py:.4f}*H*(1-1/{Z}),0,H-H/{Z})"
        x1, y2 = f"({x0}+W/{Z})", f"({y0e}+H/{Z})"
        partes.append(f"perspective=interpolation=cubic:eval=frame:x0='{x0}':y0='{y0e}':x1='{x1}':y1='{y0e}':"
                      f"x2='{x0}':y2='{y2}':x3='{x1}':y3='{y2}'")
    cor = filtro_cor(cfg)
    if cor:
        partes.append(cor)
    partes.append("format=yuv420p")
    return ",".join(partes)


def filtro_zoom_suave(Z: str, px: float = 0.5, py: float = 0.5) -> str:
    """Zoom por quadro com precisão de fração de pixel, sem o tremor do zoompan. Z = expressão do zoom (usa `in`)."""
    x0 = f"({px}*W*(1-1/{Z}))"
    y0 = f"({py}*H*(1-1/{Z}))"
    x1, y2 = f"({x0}+W/{Z})", f"({y0}+H/{Z})"
    return (f"perspective=interpolation=cubic:eval=frame:x0='{x0}':y0='{y0}':x1='{x1}':y1='{y0}':"
            f"x2='{x0}':y2='{y2}':x3='{x1}':y3='{y2}'")


def valor_em(keys: list[tuple[float, float]], t: float) -> float:
    keys = sorted(keys)
    if t <= keys[0][0]:
        return keys[0][1]
    for (ta, va), (tb, vb) in zip(keys[:-1], keys[1:]):
        if t <= tb:
            return va + (vb - va) * (t - ta) / max(tb - ta, 1e-6)
    return keys[-1][1]


# ----------------------------------------------------------------------------- direção automática
def plano_zoom(tipo: str, dur: float, C: dict, palavras_rel: list[dict] | None = None, em: float | None = None,
               valor: float | None = None, segurar: bool = False) -> list[tuple[float, float]]:
    """Pontos (t, zoom relativo ao enquadramento base) de cada movimento, com os valores medidos nos exemplos."""
    def medido(Z: dict) -> float:  # taxa por segundo dos exemplos, com teto
        return 1 + min(float(Z["max"]) - 1, float(Z["taxa_s"]) * dur)
    if tipo == "in":
        return [(0.0, 1.0), (dur, valor or medido(C["zoom_in"]))]
    if tipo == "out":
        return [(0.0, valor or medido(C["zoom_out"])), (dur, 1.0)]
    if tipo == "fixo":
        return [(0.0, valor or float(C.get("close", 1.08)))]
    if tipo == "impacto":
        I = C["impacto"]
        pico = valor or float(I["pico"])
        t_pico = em if em is not None else dur * 0.45
        ini = max(0.0, t_pico - float(I["subida"]))
        k = [(0.0, 1.0)]
        if ini > 0.05:
            k.append((ini, 1.0 + float(I.get("lento", 0.03)) * min(1.0, ini / 1.75)))
        k.append((t_pico, pico))
        if segurar:  # gancho: aperta e fica (corta para o encerramento sem voltar)
            k.append((dur, pico))
            return k
        fim_seg = min(dur, t_pico + float(I.get("segurar", 0.25)))
        k.append((fim_seg, pico))
        k.append((min(dur, fim_seg + float(I["descida"])), 1.0 + (pico - 1.0) * max(0.0, 1 - (dur - fim_seg) / float(I["descida"]))))
        return k
    return []


def momento_exclamacao(pal: list[dict]) -> float | None:
    """Fim da primeira exclamação forte da cena (tempo relativo ao corte): no gancho da história 3 o zoom chega ao
    máximo no fim de "pelo amor de Deus!"."""
    import re
    import unicodedata

    def d(s: str) -> str:
        return "".join(ch for ch in unicodedata.normalize("NFD", s) if unicodedata.category(ch) != "Mn").lower()
    texto = " ".join(d(w["w"]) for w in pal)
    for i, w in enumerate(pal):
        if w["w"].rstrip().endswith("!"):
            return w["e_rel"]
    m = re.search(r"pelo amor de deus|meu deus|nao acredito|nao pode ser|socorro", texto)
    if m:
        acum = 0
        for w in pal:
            acum += len(d(w["w"])) + 1
            if acum >= m.end():
                return w["e_rel"]
    return None
