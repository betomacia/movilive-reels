import math, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H, FPS = 1080, 1920, 30
F = '/usr/share/fonts/opentype/inter/'
def font(name, size): return ImageFont.truetype(F + name, size)
RED = (226, 24, 32); WHITE = (240, 243, 248); GRAY = (150, 160, 180)
BLUE = (110, 175, 255); GREEN = (40, 205, 115); AMBER = (255, 176, 40)

# ---------- background ----------
wp = Image.open('/mnt/user-data/uploads/470c569d-image.png').convert('RGB')
bg = Image.new('RGB', (W, H), (7, 11, 22))
side = 300
L = wp.crop((0, 0, 260, 1024)).resize((side, H)); R = wp.crop((1276, 0, 1536, 1024)).resize((side, H))
g = Image.linear_gradient('L').rotate(90).resize((side, H))
g = g.point(lambda v: int(v * 0.55))
bg.paste(L, (0, 0), g.transpose(Image.FLIP_LEFT_RIGHT)); bg.paste(R, (W - side, 0), g)
BG = np.array(bg).astype(np.float32)

logo = Image.open('/mnt/user-data/uploads/89c967e9-image.png').convert('RGBA')
arc = Image.open('/home/claude/arc_real.png').convert('RGBA')

def ease(t): t = max(0, min(1, t)); return t * t * (3 - 2 * t)
def fade(t, a, b): return ease((t - a) / max(1e-6, b - a))

def text_c(d, y, s, f, fill, alpha=1.0, img=None):
    w = d.textlength(s, font=f)
    col = tuple(int(c) for c in fill) + (int(255 * alpha),)
    d.text(((W - w) / 2, y), s, font=f, fill=col)

def bez(p0, p1, p2, t):
    return ((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])

def curve(d, p0, p1, p2, upto, fill, width):
    n = 60; pts = [bez(p0, p1, p2, i / n) for i in range(int(n * upto) + 1)]
    if len(pts) > 1: d.line(pts, fill=fill, width=width, joint='curve')

# ---------- scene timings (seconds, local reel time starts at 0 = second 8 of final) ----------
S = [(0, 4), (4, 13), (13, 18), (18, 23), (23, 27), (27, 31)]
TOTAL = 31
TOTAL_ALL = 31 + 6.3

f_big = font('InterDisplay-Bold.otf', 84); f_mid = font('InterDisplay-SemiBold.otf', 64)
f_sm = font('Inter-Medium.otf', 44); f_lab = font('Inter-SemiBold.otf', 42); f_xs = font('Inter-Medium.otf', 30)

labels = ['Móvil 1', 'Móvil 2', 'Móvil 3', 'Móvil 4', 'Móvil 5', 'Móvil 6', 'Red del lugar', 'Satélite']
NODE_X, Y0, DY = 372, 640, 92
nodes = [(NODE_X, Y0 + i * DY) for i in range(8)]
MERGE = (760, Y0 + 3.5 * DY); OUT = (900, MERGE[1])

# ---------- light engine (fibra óptica) ----------
def mix(c1, c2, k): return tuple(c1[i] * (1 - k) + c2[i] * k for i in range(3))
def sc(c, k): return tuple(int(max(0, min(255, v * k))) for v in c)

def new_light():
    Lg = Image.new('RGB', (W, H), (0, 0, 0)); return Lg, ImageDraw.Draw(Lg)

def bloom(Lg):
    a = np.asarray(Lg, np.float32)
    b1 = np.asarray(Lg.filter(ImageFilter.GaussianBlur(4)), np.float32)
    s = Lg.resize((W // 4, H // 4), Image.BILINEAR)
    b2 = np.asarray(s.filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR), np.float32)
    b3 = np.asarray(s.filter(ImageFilter.GaussianBlur(10)).resize((W, H), Image.BILINEAR), np.float32)
    return a + 1.2 * b1 + 2.0 * b2 + 1.7 * b3

def glow_dot(dl, p, r, col):
    dl.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=sc(col, 1))

def comet(dl, pts, u, col, n=16, step=0.010, r0=7.0):
    N = len(pts) - 1
    for j in range(n, -1, -1):
        uu = u - j * step
        if uu < 0 or uu > 1: continue
        p = pts[int(uu * N)]
        k = 1 - j / (n + 1)
        glow_dot(dl, p, max(1.5, r0 * k), sc(mix(col, (255, 255, 255), 0.75 * k), 0.35 + 0.65 * k))

def fiber(dl, pts, upto, col, inten=1.0):
    n = int((len(pts) - 1) * upto) + 1
    if n < 2: return
    seg = pts[:n]
    dl.line(seg, fill=sc(col, 0.55 * inten), width=9, joint='curve')
    dl.line(seg, fill=sc(mix(col, (255, 255, 255), 0.55), 0.95 * inten), width=3, joint='curve')

def sparks(dl, p, k, col, seed, n=12, dist=70):
    rng = np.random.default_rng(seed)
    for s in range(n):
        ang = rng.uniform(0, 2 * math.pi); sp = rng.uniform(0.4, 1.0)
        rr = dist * sp * k
        q = (p[0] + rr * math.cos(ang), p[1] + rr * math.sin(ang))
        q2 = (p[0] + rr * 0.6 * math.cos(ang), p[1] + rr * 0.6 * math.sin(ang))
        e = (1 - k) ** 1.5
        dl.line((q2, q), fill=sc(mix(col, (255, 230, 200), 0.4), e), width=3)

FIB_PTS = []
for (nx, ny) in nodes:
    FIB_PTS.append([bez((nx + 12, ny), (MERGE[0] - 200, ny), MERGE, i / 160) for i in range(161)])
TRUNK = [(MERGE[0] + (OUT[0] - MERGE[0]) * i / 40, MERGE[1]) for i in range(41)]

def draw_paths(dl, d, t_build, tt, failed=(), fail_a=0.0, pulse=0.0):
    """dl = capa de luz (aditiva), d = capa de textos/marcas"""
    for i, (nx, ny) in enumerate(nodes):
        a = fade(t_build, i * 0.55, i * 0.55 + 0.9)
        if a <= 0: continue
        sat = i == 7
        dead = i in failed
        col = (90, 165, 255) if not sat else (175, 130, 255)
        inten = 1.0
        if dead:
            flick = 0.5 + 0.5 * math.sin(tt * 47 + i * 3) * math.sin(tt * 23)
            inten = (1 - fail_a) * (0.6 + 0.4 * flick) + 0.10 * fail_a
            col = mix(col, (60, 70, 95), fail_a)
        lab_col = GRAY if not dead else tuple(int(GRAY[k] * (1 - fail_a) + 80 * fail_a) for k in range(3))
        d.text((62, ny - 25), labels[i], font=f_lab, fill=lab_col + (int(255 * a),))
        pts = FIB_PTS[i]
        fiber(dl, pts, a, col, inten)
        # punto de origen
        glow_dot(dl, (nx, ny), 13, sc(col, 0.8 * inten))
        glow_dot(dl, (nx, ny), 6, sc(mix(col, (255, 255, 255), 0.8), inten))
        if a < 1:  # cabeza luminosa mientras se tiende la fibra
            comet(dl, pts, a, col, n=10, step=0.012, r0=9)
        elif not dead or fail_a < 0.15:
            for k in range(3):
                u = (tt * 0.55 + k / 3 + i * 0.137) % 1.0
                comet(dl, pts, u, col)
        if dead:
            bp = pts[45]
            if 0 < fail_a < 1: sparks(dl, bp, fail_a, RED, seed=i)
            if fail_a > 0.3:
                k = int(255 * min(1, (fail_a - 0.3) / 0.4)); x, y = bp
                d.line((x - 16, y - 16, x + 16, y + 16), fill=RED + (k,), width=7)
                d.line((x - 16, y + 16, x + 16, y - 16), fill=RED + (k,), width=7)
    a_out = fade(t_build, 4.6, 5.6)
    if a_out > 0:
        fiber(dl, TRUNK, a_out, (255, 40, 50), 1.0)
        dl.line(TRUNK[:max(2, int(40 * a_out) + 1)], fill=(255, 60, 60), width=12)
        dl.line(TRUNK[:max(2, int(40 * a_out) + 1)], fill=(255, 225, 225), width=4)
        if a_out >= 1:
            for k in range(4):
                u = (tt * 1.6 + k / 4) % 1.0
                comet(dl, TRUNK, u, (255, 60, 60), n=10, step=0.03, r0=8)
        R2 = 46 + 5 * pulse
        glow_dot(dl, OUT, R2 + 8, sc(RED, 0.9 * a_out))
        # ondas que salen del nodo
        for k in range(3):
            ph = (tt * 0.9 + k / 3) % 1.0
            rr = R2 + 10 + 75 * ph
            dl.ellipse((OUT[0] - rr, OUT[1] - rr, OUT[0] + rr, OUT[1] + rr), outline=sc(RED, a_out * (1 - ph) * 0.9), width=3)
        dd = d
        dd.ellipse((OUT[0] - R2, OUT[1] - R2, OUT[0] + R2, OUT[1] + R2), fill=RED + (int(255 * a_out),))
        fm = font('InterDisplay-Black.otf', 52)
        tw = dd.textlength('m', font=fm)
        dd.text((OUT[0] - tw / 2, OUT[1] - 36), 'm', font=fm, fill=WHITE + (int(255 * a_out),))


# ---------- HOOK (v3): monitor en directo -> se corta ----------
HOOK = 6.3
MW, MH = 900, 506
MX, MY = (W - MW) // 2, 600

def mon_partido(t):
    im = Image.new('RGB', (MW, MH), (30, 110, 50)); d = ImageDraw.Draw(im)
    for k in range(9):
        if k % 2: d.rectangle((k * MW // 9, 0, (k + 1) * MW // 9, MH), fill=(36, 124, 58))
    wl = (225, 235, 225)
    d.rectangle((30, 30, MW - 30, MH - 30), outline=wl, width=4)
    d.line((MW // 2, 30, MW // 2, MH - 30), fill=wl, width=4)
    d.ellipse((MW // 2 - 70, MH // 2 - 70, MW // 2 + 70, MH // 2 + 70), outline=wl, width=4)
    d.rectangle((30, MH // 2 - 110, 140, MH // 2 + 110), outline=wl, width=4)
    d.rectangle((MW - 140, MH // 2 - 110, MW - 30, MH // 2 + 110), outline=wl, width=4)
    rng = np.random.default_rng(3)
    for i in range(14):
        bx, by = rng.uniform(120, MW - 120), rng.uniform(70, MH - 70)
        ph = rng.uniform(0, 6)
        x = bx + 40 * math.sin(t * 1.3 + ph); y = by + 25 * math.cos(t * 1.1 + ph)
        c = (230, 40, 45) if i < 7 else (240, 240, 245)
        d.ellipse((x - 11, y - 11, x + 11, y + 11), fill=c)
    bxx = MW / 2 + 160 * math.sin(t * 1.7); byy = MH / 2 + 60 * math.sin(t * 2.3)
    d.ellipse((bxx - 7, byy - 7, bxx + 7, byy + 7), fill=(255, 255, 255))
    d.rounded_rectangle((24, 22, 250, 66), 8, fill=(10, 14, 30))
    d.text((40, 28), 'LOC  1 - 0  VIS', font=font('Inter-Bold.otf', 26), fill=(255, 255, 255))
    return im

def mon_informativo(t):
    im = Image.new('RGB', (MW, MH), (60, 90, 140)); d = ImageDraw.Draw(im)
    for y in range(MH):
        k = y / MH; d.line((0, y, MW, y), fill=(int(70 + 60 * k), int(100 + 50 * k), int(160 + 30 * k)))
    rng = np.random.default_rng(7); x = 0
    while x < MW:
        bw = int(rng.uniform(50, 110)); bh = int(rng.uniform(120, 300))
        d.rectangle((x, MH - 60 - bh, x + bw - 6, MH - 60), fill=(40, 52, 80))
        for wy in range(MH - 50 - bh, MH - 70, 26):
            for wx in range(x + 10, x + bw - 16, 20):
                if rng.random() > 0.5: d.rectangle((wx, wy, wx + 8, wy + 12), fill=(250, 220, 140))
        x += bw
    d.rectangle((0, MH - 60, MW, MH), fill=(55, 58, 66))
    cx, cy = 330, 210 + 3 * math.sin(t * 2)
    d.rounded_rectangle((cx - 85, cy + 60, cx + 85, MH), 40, fill=(25, 32, 55))
    d.ellipse((cx - 50, cy - 40, cx + 50, cy + 60), fill=(205, 160, 130))
    d.pieslice((cx - 54, cy - 46, cx + 54, cy + 40), 180, 360, fill=(50, 35, 30))
    d.rounded_rectangle((cx + 40, cy + 70, cx + 62, cy + 150), 8, fill=(20, 20, 24))
    d.ellipse((cx + 30, cy + 45, cx + 72, cy + 87), fill=(226, 24, 32))
    d.rectangle((0, MH - 120, MW, MH - 70), fill=(226, 24, 32))
    d.text((24, MH - 113), 'ÚLTIMA HORA', font=font('InterDisplay-Bold.otf', 32), fill=(255, 255, 255))
    d.rectangle((0, MH - 70, MW, MH - 30), fill=(245, 245, 248))
    d.text((24, MH - 66), 'Conexión en directo desde el lugar de los hechos', font=font('Inter-SemiBold.otf', 26), fill=(20, 24, 36))
    return im

def mon_streaming(t):
    im = Image.new('RGB', (MW, MH), (14, 16, 30)); d = ImageDraw.Draw(im)
    for k in range(5):
        x = 120 + k * 165; a = 0.5 + 0.5 * math.sin(t * 3 + k)
        d.polygon([(x - 8, 0), (x + 8, 0), (x + 90, MH - 120), (x - 90, MH - 120)], fill=(int(40 + 40 * a), int(40 + 40 * a), int(70 + 60 * a)))
    d.rounded_rectangle((180, 50, MW - 180, 270), 10, fill=(30, 50, 100), outline=(110, 175, 255), width=3)
    pts = [(220 + i * 46, 230 - 120 * (0.5 + 0.5 * math.sin(i * 0.9 + 1)) * (i / 10 + 0.4)) for i in range(11)]
    d.line(pts, fill=(110, 175, 255), width=6, joint='curve')
    d.rectangle((0, MH - 120, MW, MH), fill=(28, 30, 48))
    cx = 450; d.ellipse((cx - 32, 300, cx + 32, 364), fill=(200, 155, 125))
    d.rounded_rectangle((cx - 60, 360, cx + 60, MH - 70), 30, fill=(70, 75, 95))
    d.polygon([(cx - 80, MH - 140), (cx + 80, MH - 140), (cx + 60, MH), (cx - 60, MH)], fill=(226, 24, 32))
    for k in range(3):
        y = 120 + k * 70 - (t * 30 % 70)
        d.rounded_rectangle((MW - 160, y, MW - 20, y + 50), 14, fill=(50, 56, 84))
        d.rounded_rectangle((MW - 145, y + 15, MW - 45 - k * 20, y + 33), 6, fill=(150, 160, 190))
    return im

def bars_img():
    im = Image.new('RGB', (MW, MH)); d = ImageDraw.Draw(im)
    cols = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0), (192, 0, 192), (192, 0, 0), (0, 0, 192)]
    bw = MW / 7
    for i, c in enumerate(cols): d.rectangle((int(i * bw), 0, int((i + 1) * bw), int(MH * 0.72)), fill=c)
    rev = [(0, 0, 192), (19, 19, 19), (192, 0, 192), (19, 19, 19), (0, 192, 192), (19, 19, 19), (192, 192, 192)]
    for i, c in enumerate(rev): d.rectangle((int(i * bw), int(MH * 0.72), int((i + 1) * bw), int(MH * 0.8)), fill=c)
    d.rectangle((0, int(MH * 0.8), MW, MH), fill=(16, 16, 16))
    return im
BARS = bars_img()

def glitch(im, k, seed):
    a = np.asarray(im).copy(); rng = np.random.default_rng(seed)
    for _ in range(int(6 + 18 * k)):
        y0 = int(rng.uniform(0, MH - 10)); h = int(rng.uniform(4, 40)); sh = int(rng.uniform(-120, 120) * k)
        a[y0:y0 + h] = np.roll(a[y0:y0 + h], sh, axis=1)
    out = a.copy(); s = int(14 * k)
    out[:, :, 0] = np.roll(a[:, :, 0], s, axis=1); out[:, :, 2] = np.roll(a[:, :, 2], -s, axis=1)
    noise = rng.integers(0, int(90 * k) + 1, a.shape[:2])[..., None]
    return Image.fromarray(np.clip(out.astype(int) + noise - int(45 * k), 0, 255).astype(np.uint8))

T_CUT = 5.25
def hook_frame(t, d, dl, ov):
    a = fade(t, 0, 0.25) * (1 - fade(t, HOOK - 0.35, HOOK))
    if t < 1.3: scr = mon_partido(t); cap = 'Un partido.'
    elif t < 2.45: scr = mon_informativo(t); cap = 'Un informativo.'
    else: scr = mon_streaming(t); cap = 'Un streaming.'
    if t >= T_CUT:
        g = t - T_CUT
        if g < 0.45: scr = glitch(mon_streaming(T_CUT), 1.0 - 0.3 * g, int(t * 30))
        else: scr = glitch(BARS, 0.08, int(t * 30))
    elif t > T_CUT - 0.5:
        scr = glitch(scr, 0.25 * fade(t, T_CUT - 0.5, T_CUT), int(t * 30))
    # marco del monitor
    d.rounded_rectangle((MX - 22, MY - 22, MX + MW + 22, MY + MH + 22), 26, fill=(22, 26, 40, int(255 * a)), outline=(70, 80, 110, int(255 * a)), width=3)
    s2 = scr.convert('RGBA'); s2.putalpha(int(255 * a)); ov.alpha_composite(s2, (MX, MY))
    # tally EN DIRECTO / SIN SEÑAL
    cut = t >= T_CUT
    pc = (226, 24, 32) if not cut else (70, 75, 90)
    blink = 1.0 if not cut else 1.0
    d.rounded_rectangle((MX, MY - 100, MX + 290, MY - 38), 31, fill=pc + (int(255 * a),))
    d.ellipse((MX + 22, MY - 82, MX + 48, MY - 56), fill=(255, 255, 255, int(255 * a * (0.55 + 0.45 * math.sin(t * 9)) if not cut else 90 * a)))
    d.text((MX + 62, MY - 92), 'EN DIRECTO', font=font('InterDisplay-Bold.otf', 38), fill=WHITE + (int(255 * a),))
    if not cut: glow_dot(dl, (MX + 35, MY - 69), 20, sc(RED, 0.9 * a))
    if t >= T_CUT + 0.45:
        k = fade(t, T_CUT + 0.45, T_CUT + 0.6) * a
        f = font('InterDisplay-Black.otf', 70); tw = d.textlength('SIN SEÑAL', font=f)
        d.rounded_rectangle((W / 2 - tw / 2 - 30, MY + MH / 2 - 60, W / 2 + tw / 2 + 30, MY + MH / 2 + 52), 14, fill=(10, 12, 20, int(230 * k)))
        d.text((W / 2 - tw / 2, MY + MH / 2 - 50), 'SIN SEÑAL', font=f, fill=RED + (int(255 * k),))
    # textos
    if t < 3.75:
        text_c(d, 1200, cap, f_big, WHITE, a)
    elif t < T_CUT:
        text_c(d, 1200, 'Emitiendo en vivo…', f_big, WHITE, a * fade(t, 3.75, 4.0))
    else:
        text_c(d, 1200, '…y se corta.', f_big, RED, a * fade(t, T_CUT, T_CUT + 0.15))


# ---------- SUBTÍTULOS (v4) ----------
import json as _json
WORDS = _json.load(open('/home/claude/reel/reel1_words.json'))
def _chunks(words, maxw=3, gap=0.35):
    out, cur = [], []
    for w in words:
        if cur and (len(cur) >= maxw or w[1] - cur[-1][2] > gap or cur[-1][0][-1] in '.,:?!…'):
            out.append(cur); cur = []
        cur.append(w)
    if cur: out.append(cur)
    return out
CHUNKS = _chunks(WORDS)
f_cap = font('InterDisplay-Bold.otf', 46)
CAP_Y = 1402
SAFE_CX = 491
def draw_caps(d, t):
    for ci, ch in enumerate(CHUNKS):
        t0 = ch[0][1] - 0.06
        nxt = CHUNKS[ci + 1][0][1] - 0.06 if ci + 1 < len(CHUNKS) else 1e9
        t1 = min(ch[-1][2] + 0.35, nxt)
        if not (t0 <= t < t1): continue
        words = [w[0] for w in ch]
        sp = d.textlength(' ', font=f_cap)
        widths = [d.textlength(w, font=f_cap) for w in words]
        tw = sum(widths) + sp * (len(words) - 1)
        x = SAFE_CX - tw / 2
        d.rounded_rectangle((x - 22, CAP_Y - 10, x + tw + 22, CAP_Y + 62), 16, fill=(8, 10, 20, 205))
        for w, ww, wd in zip(words, widths, ch):
            active = wd[1] - 0.04 <= t < wd[2] + 0.12
            d.text((x, CAP_Y), w, font=f_cap, fill=(RED if active else WHITE) + (255,))
            x += ww + sp
        return


# ---------- ZONA SEGURA (v5) ----------
CROP = (60, 300, 1040, 1580)
SC = 0.85
DST = (75, 302)
CW, CH = int((CROP[2] - CROP[0]) * SC), int((CROP[3] - CROP[1]) * SC)
_lg = logo.resize((int(logo.width * 66 / logo.height), 66), Image.LANCZOS)
LOGO_SMALL = _lg; LOGO_POS = (SAFE_CX - _lg.width // 2, 226)
END_START = HOOK + 27.0

def compose(ov, LG, la, tg):
    light = np.clip(bloom(LG) * la, 0, 255).astype(np.uint8)
    lim = Image.fromarray(light).crop(CROP).resize((CW, CH), Image.LANCZOS)
    lfull = Image.new('RGB', (W, H), (0, 0, 0)); lfull.paste(lim, DST)
    base = BG + np.asarray(lfull, np.float32)
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert('RGBA')
    oim = ov.crop(CROP).resize((CW, CH), Image.LANCZOS)
    img.alpha_composite(oim, DST)
    top = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dt = ImageDraw.Draw(top)
    draw_caps(dt, tg)
    ka = 1 - fade(tg, END_START - 0.2, END_START + 0.3)
    if ka > 0:
        lg = LOGO_SMALL.copy(); lg.putalpha(LOGO_SMALL.split()[3].point(lambda v: int(v * ka * fade(tg, 0, 0.4))))
        top.alpha_composite(lg, LOGO_POS)
    img.alpha_composite(top)
    return img.convert('RGB')

def frame(t):
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    LG, dl = new_light(); la = 1.0
    tg = t
    if t < HOOK:
        hook_frame(t, d, dl, ov)
        return compose(ov, LG, 1.0, tg)
    t = t - HOOK
    # --- scene 0: single connection breaks ---
    if t < S[0][1]:
        lt = t
        a = fade(lt, 0, 0.5) * (1 - fade(lt, 3.6, 4.0))
        text_c(d, 560, 'El problema:', f_mid, GRAY, a)
        text_c(d, 640, 'depender de una', f_big, WHITE, a)
        text_c(d, 730, 'sola conexión.', f_big, WHITE, a)
        y = 1060; x0, x1 = 140, 940
        prog = fade(lt, 0.4, 1.6)
        brk = fade(lt, 2.0, 2.4)
        xm = (x0 + x1) / 2
        la = a
        line_pts = [(x0 + (x1 - x0) * i / 100, y) for i in range(101)]
        if brk <= 0:
            fiber(dl, line_pts, prog, (90, 165, 255))
            if prog < 1: comet(dl, line_pts, prog, (90, 165, 255), n=12, step=0.015, r0=10)
            else:
                for k in range(3): comet(dl, line_pts, (lt * 0.7 + k / 3) % 1, (90, 165, 255), step=0.012)
        else:
            gap = 40 * brk
            flick = 0.55 + 0.45 * math.sin(lt * 50) * math.sin(lt * 21)
            dim = (1 - brk) * flick + 0.12 * brk
            colb = mix((90, 165, 255), (60, 70, 95), brk)
            fiber(dl, [(x0, y), (xm - gap, y + 10 * brk)], 1, colb, dim)
            fiber(dl, [(xm + gap, y - 10 * brk), (x1, y)], 1, colb, dim)
            sk = fade(lt, 2.0, 3.0)
            if sk < 1: sparks(dl, (xm, y), sk, RED, seed=99, n=22, dist=150)
            glow_dot(dl, (xm, y), 10 + 30 * (1 - sk), sc(RED, 1 - sk))
            text_c(d, 1160, 'Señal perdida', f_sm, RED, a * brk)
    # --- scene 1: 8 paths merge ---
    elif t < S[1][1]:
        lt = t - S[1][0]
        a = 1 - fade(lt, 8.6, 9.0)
        text_c(d, 330, '6 redes móviles', f_mid, WHITE, fade(lt, 0, 0.5) * a)
        text_c(d, 400, '+ la conexión del lugar', f_mid, WHITE, fade(lt, 0.3, 0.8) * a)
        text_c(d, 470, '+ satélite (opcional)', f_mid, GRAY, fade(lt, 0.6, 1.1) * a)
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dlay = ImageDraw.Draw(lay)
        draw_paths(dl, dlay, lt - 0.6, lt, pulse=0.5 + 0.5 * math.sin(lt * 4)); la = a
        ov.alpha_composite(Image.fromarray((np.array(lay) * np.array([1, 1, 1, a])).astype(np.uint8)))
        text_c(d, 1440, '= una sola conexión', f_big, RED, fade(lt, 5.6, 6.3) * a)
    # --- scene 2: two fail, still on air ---
    elif t < S[2][1]:
        lt = t - S[2][0]
        a = fade(lt, 0, 0.3) * (1 - fade(lt, 4.6, 5.0))
        fa = fade(lt, 0.6, 1.4)
        lay = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dlay = ImageDraw.Draw(lay)
        draw_paths(dl, dlay, 99, lt + 9, failed=(1, 6), fail_a=fa, pulse=0.5 + 0.5 * math.sin(lt * 5)); la = a
        ov.alpha_composite(Image.fromarray((np.array(lay) * np.array([1, 1, 1, a])).astype(np.uint8)))
        text_c(d, 330, 'Si una falla,', f_big, WHITE, a)
        text_c(d, 422, 'las demás sostienen', f_mid, WHITE, a)
        text_c(d, 486, 'la transmisión.', f_mid, WHITE, a)
        sa = fade(lt, 1.6, 2.2) * a
        bx = 300; by = 1450
        d.rounded_rectangle((bx, by, W - bx, by + 90), 45, fill=(20, 120, 70, int(230 * sa)))
        d.ellipse((bx + 30, by + 30, bx + 60, by + 60), fill=(255, 255, 255, int(255 * sa * (0.6 + 0.4 * math.sin(lt * 8)))))
        d.text((bx + 85, by + 20), 'EN DIRECTO', font=font('InterDisplay-Bold.otf', 46), fill=WHITE + (int(255 * sa),))
    # --- scene 3: control center ---
    elif t < S[3][1]:
        lt = t - S[3][0]
        a = fade(lt, 0, 0.4) * (1 - fade(lt, 4.6, 5.0))
        px0, py0, px1 = 120, 470, W - 120
        d.rounded_rectangle((px0, py0, px1, py0 + 880), 28, fill=(14, 20, 36, int(235 * a)), outline=(60, 75, 110, int(255 * a)), width=2)
        d.text((px0 + 40, py0 + 30), 'Supervisión en directo', font=font('InterDisplay-SemiBold.otf', 44), fill=WHITE + (int(255 * a),))
        d.ellipse((px1 - 80, py0 + 45, px1 - 52, py0 + 73), fill=RED + (int(255 * a * (0.5 + 0.5 * math.sin(lt * 6))),))
        for i, lab in enumerate(labels):
            y = py0 + 130 + i * 88
            ra = fade(lt, 0.2 + i * 0.12, 0.6 + i * 0.12) * a
            d.text((px0 + 40, y), lab, font=f_lab, fill=GRAY + (int(255 * ra),))
            warn = i in (1, 6) and lt < 2.6
            col = AMBER if warn else GREEN
            level = 0.55 + 0.35 * (0.5 + 0.5 * math.sin(lt * 3 + i))
            if warn: level = 0.15
            bx0, bx1 = px0 + 330, px1 - 215
            d.rounded_rectangle((bx0, y + 8, bx1, y + 34), 13, fill=(40, 48, 66, int(255 * ra)))
            d.rounded_rectangle((bx0, y + 8, bx0 + (bx1 - bx0) * level, y + 34), 13, fill=col + (int(255 * ra),))
            st = 'REVISANDO' if warn else 'OK'
            sf = font('Inter-Bold.otf', 26 if warn else 32)
            d.text((px1 - 200, y + 2), st, font=sf, fill=col + (int(255 * ra),))
        text_c(d, 1385, 'Un equipo técnico', f_big, WHITE, fade(lt, 1.0, 1.6) * a)
        text_c(d, 1472, 'supervisa tu señal en directo.', f_mid, WHITE, fade(lt, 1.2, 1.8) * a)
    # --- scene 4: claim ---
    elif t < S[4][1]:
        lt = t - S[4][0]
        a = fade(lt, 0, 0.5) * (1 - fade(lt, 3.6, 4.0))
        fb = font('InterDisplay-Black.otf', 104)
        text_c(d, 760, 'En directo,', fb, WHITE, a)
        text_c(d, 880, 'con confianza.', fb, RED, fade(lt, 0.3, 0.8) * a)
        lw = 420 * fade(lt, 0.8, 1.4)
        if lw > 2:
            fiber(dl, [(W / 2 - lw, 1030), (W / 2 + lw, 1030)], 1, (255, 50, 60)); la = a
            u = (lt * 0.8) % 1; comet(dl, [(W / 2 - lw + 2 * lw * i / 100, 1030) for i in range(101)], u, (255, 60, 60), step=0.012)
    # --- scene 5: end card ---
    else:
        lt = t - S[5][0]
        a = fade(lt, 0, 0.5)
        text_c(d, 470, 'Cuéntanos tu caso.', font('InterDisplay-Bold.otf', 80), WHITE, a)
        text_c(d, 575, 'Escríbenos por mensaje directo', f_sm, WHITE, a)
        text_c(d, 625, 'info@movilive.com', f_sm, GRAY, a)
        lw = 860; lh = int(logo.height * lw / logo.width)
        lg = logo.resize((lw, lh), Image.LANCZOS)
        la = fade(lt, 0.3, 0.9)
        lg2 = lg.copy(); lg2.putalpha(lg.split()[3].point(lambda v: int(v * la)))
        ov.alpha_composite(lg2, ((W - lw) // 2, 820))
        text_c(d, 820 + lh + 50, 'Inteligencia creativa para el', f_sm, WHITE, fade(lt, 0.8, 1.3))
        text_c(d, 820 + lh + 100, 'mundo audiovisual y digital', f_sm, WHITE, fade(lt, 0.8, 1.3))
        text_c(d, 1420, '@movilive.global', f_mid, RED, fade(lt, 1.1, 1.6))
    return compose(ov, LG, la, tg)

if __name__ == '__main__':
    out = sys.argv[1]
    if len(sys.argv) > 2:  # preview stills
        for tt in [float(x) for x in sys.argv[2].split(',')]:
            frame(tt).save(f'{out}_{tt:05.1f}.png')
        sys.exit()
    p = subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                          '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', out], stdin=subprocess.PIPE)
    for i in range(int(round(TOTAL_ALL * FPS))):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close(); p.wait()
