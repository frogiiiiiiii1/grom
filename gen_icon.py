"""Генератор иконки grom v3 — премиум-стиль.

* Форма — squircle (суперэллипс), как у современных системных иконок
* Глубокий диагональный градиент: лаванда -> фиолет -> тёмный индиго,
  с тёплым магента-бликом в нижнем левом углу
* Стеклянная молния с фаской (свет сверху-слева, тень снизу-справа),
  двойное свечение и мягкая тень
* Тонкие волны-удары вокруг («grom» = грохот)
* Световой ободок по ребру и внутренняя виньетка для объёма
* Превью на тёмном и светлом фоне с подписями размеров
"""
import math
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

S = 1024
N_SUPER = 4.5          # крутизна squircle
OUT = "grom_icon"

# основные цвета
C_TOP = (0xD8, 0xCF, 0xFF)      # лаванда сверху-слева
C_MID = (0x7A, 0x5C, 0xFF)      # яркий фиолет
C_BOT = (0x23, 0x15, 0x82)      # глубокий индиго снизу-справа
C_MAGENTA = (0xFF, 0x5C, 0xBE)  # тёплый акцент


def superellipse_mask(size, n=N_SUPER, center=(0, 0), span=None):
    """Маска squircle, нарисованная строками (без numpy)."""
    span = span or size
    cx, cy = center
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    half = span / 2.0
    for y in range(size):
        dy = abs((y + 0.5 - cy) / half)
        if dy >= 1:
            continue
        t = 1.0 - dy ** n
        if t <= 0:
            continue
        dx = (t ** (1.0 / n)) * half
        d.line([(cx - dx, y), (cx + dx, y)], fill=255)
    return m


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ------------------------------------------------------------------ фон
base = Image.new("RGB", (S, S))
bd = ImageDraw.Draw(base)
# диагональный градиент из трёх стопов (покадрово по строке)
for y in range(S):
    row = []
    for x in range(0, S, 4):
        t = (x + y) / (2.0 * (S - 1))
        t = t ** 1.06
        if t < 0.55:
            c = lerp(C_TOP, C_MID, t / 0.55)
        else:
            c = lerp(C_MID, C_BOT, (t - 0.55) / 0.45)
        row.append(c)
    for i, c in enumerate(row):
        x0 = i * 4
        bd.rectangle([x0, y, x0 + 3, y], fill=c)

# магента-бликом в нижнем левом углу (тёплая «энергия»)
mag = Image.new("L", (S, S), 0)
ImageDraw.Draw(mag).ellipse([-330, 620, 420, 1380], fill=150)
mag = mag.filter(ImageFilter.GaussianBlur(190))
base = Image.composite(Image.new("RGB", (S, S), C_MAGENTA), base,
                       mag.point(lambda v: int(v * 0.45)))

# крупный блик сверху-слева
spec = Image.new("L", (S, S), 0)
ImageDraw.Draw(spec).ellipse([-340, -390, 660, 430], fill=140)
spec = spec.filter(ImageFilter.GaussianBlur(150))
base = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), base,
                       spec.point(lambda v: int(v * 0.58)))

# стеклянный блик по верхней дуге
gloss = Image.new("L", (S, S), 0)
ImageDraw.Draw(gloss).ellipse([-160, -600, 1184, 350], fill=52)
gloss = gloss.filter(ImageFilter.GaussianBlur(64))
base = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), base,
                       gloss.point(lambda v: int(v * 0.72)))

# тень справа-снизу
shade = Image.new("L", (S, S), 0)
ImageDraw.Draw(shade).ellipse([400, 400, 1420, 1420], fill=140)
shade = shade.filter(ImageFilter.GaussianBlur(230))
base = Image.composite(Image.new("RGB", (S, S), (20, 10, 74)), base,
                       shade.point(lambda v: int(v * 0.78)))

# ------------------------------------------------------------------ молния
CX, CY = 518.0, 512.0
PTS = [(636, 128), (320, 574), (516, 574),
       (396, 896), (716, 452), (540, 452)]
K = 1.08                                     # чуть крупнее
PTS = [(CX + (x - CX) * K, CY + (y - CY) * K) for x, y in PTS]

bolt = Image.new("L", (S, S), 0)
ImageDraw.Draw(bolt).polygon(PTS, fill=255)
bolt = bolt.filter(ImageFilter.GaussianBlur(17))
bolt = bolt.point(lambda v: 255 if v > 127 else 0)   # скруглённые углы
bolt_aa = bolt.filter(ImageFilter.GaussianBlur(2))   # гладкий край

# волны-удары позади молнии
for r, w, a in ((350, 8, 42), (436, 5, 26)):
    ring = Image.new("L", (S, S), 0)
    ImageDraw.Draw(ring).ellipse([S / 2 - r, S / 2 - r, S / 2 + r, S / 2 + r],
                                 outline=255, width=w)
    ring = ring.filter(ImageFilter.GaussianBlur(4)).point(
        lambda v, a=a: int(v * a / 100))
    base = Image.composite(Image.new("RGB", (S, S), (230, 226, 255)), base,
                           ring)

# мягкая тень молнии
shadow = Image.new("L", (S, S), 0)
shadow.paste(bolt, (0, 22))
shadow = shadow.filter(ImageFilter.GaussianBlur(36)).point(
    lambda v: int(v * 0.58))
base = Image.composite(Image.new("RGB", (S, S), (12, 6, 44)), base, shadow)

# двойное свечение: фиолетовый ореол + белое ядро
halo2 = bolt.filter(ImageFilter.GaussianBlur(120)).point(
    lambda v: int(v * 0.34))
base = Image.composite(Image.new("RGB", (S, S), (178, 160, 255)), base, halo2)
halo1 = bolt.filter(ImageFilter.GaussianBlur(46)).point(
    lambda v: int(v * 0.55))
base = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), base, halo1)

# тело молнии: диагональный градиент белый -> светлая лаванда
body = Image.new("RGB", (S, S))
bbd = ImageDraw.Draw(body)
for y in range(S):
    for x in range(0, S, 4):
        t = ((x + y) / (2.0 * (S - 1))) ** 1.15
        c = lerp((255, 255, 255), (0xDD, 0xD4, 0xFF), t)
        bbd.rectangle([x, y, x + 3, y], fill=c)
img = Image.composite(body, base, bolt_aa)


def shift(im, dx, dy):
    out = Image.new("L", im.size, 0)
    out.paste(im, (dx, dy))
    return out


# фаска: светлое ребро сверху-слева
light = ImageChops.subtract(bolt, shift(bolt, 7, 7)).filter(
    ImageFilter.GaussianBlur(5)).point(lambda v: int(v * 0.75))
img = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), img, light)
# фаска: тень снизу-справа
dark = ImageChops.subtract(bolt, shift(bolt, -7, -7)).filter(
    ImageFilter.GaussianBlur(5)).point(lambda v: int(v * 0.55))
img = Image.composite(Image.new("RGB", (S, S), (86, 74, 180)), img, dark)

# ------------------------------------------------------------------ рёбра
# тёмная кромка внутри края (контраст на светлом фоне)
edge = Image.new("L", (S, S), 0)
ImageDraw.Draw(edge).rounded_rectangle([10, 10, S - 11, S - 11],
                                       radius=210, outline=255, width=16)
edge = edge.filter(ImageFilter.GaussianBlur(7)).point(lambda v: int(v * 0.55))
img = Image.composite(Image.new("RGB", (S, S), (14, 8, 52)), img, edge)

# световой ободок: яркий сверху-слева, таает внизу-справа
rim = Image.new("L", (S, S), 0)
ImageDraw.Draw(rim).rounded_rectangle([16, 16, S - 17, S - 17],
                                      radius=204, outline=255, width=6)
rim = rim.filter(ImageFilter.GaussianBlur(2))
fade = Image.new("L", (S, S), 0)
fd = ImageDraw.Draw(fade)
for y in range(S):
    v = int(255 * max(0.0, 1.15 - 1.5 * y / (S - 1)))
    fd.line([(0, y), (S, y)], fill=v)
rim = ImageChops.multiply(rim, fade).point(lambda v: int(v * 0.85))
img = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), img, rim)

# ------------------------------------------------------------------ маска
# центр маски — середина холста (раньше был (0,0) — иконка обрезалась углом)
mask = superellipse_mask(S * 2, center=(S, S)).resize((S, S), Image.LANCZOS)
img = img.convert("RGBA")
img.putalpha(mask)

# ------------------------------------------------------------------ сохранение
img.save(f"{OUT}.png")
img.save(f"{OUT}.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                              (64, 64), (128, 128), (256, 256)])


# ------------------------------------------------------------------- превью
def font(size, bold=False):
    name = "segoeuib.ttf" if bold else "segoeui.ttf"
    try:
        return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
    except OSError:
        return ImageFont.load_default()


PW, PH = 470, 300
prev = Image.new("RGB", (PW, PH))
pd = ImageDraw.Draw(prev)
for y in range(PH):                       # тёмный градиентный фон
    t = y / (PH - 1)
    pd.line([(0, y), (PW, y)], fill=lerp((0x0C, 0x0E, 0x14),
                                         (0x17, 0x1B, 0x28), t))

big = img.resize((236, 236), Image.LANCZOS)
# подложка-тень под большой иконкой
sh = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
sh.paste((0, 0, 0, 120), (32, 44, 32 + 236, 44 + 236), big.split()[3])
prev.paste(Image.alpha_composite(prev.convert("RGBA"),
                                 sh.filter(ImageFilter.GaussianBlur(18))
                                 ).convert("RGB"), (0, 0))
prev.paste(big, (24, 34), big)

pd.text((286, 34), "grom", font=font(26, True), fill=(255, 255, 255))
pd.text((286, 64), "обходник", font=font(17), fill=(150, 152, 168))

x = 286
for s in (64, 32, 16):
    sm = img.resize((s, s), Image.LANCZOS)
    prev.paste(sm, (x, 128 + (64 - s) // 2), sm)
    pd.text((x, 200), f"{s}px", font=font(12), fill=(120, 124, 142))
    x += s + 20

# светлая плашка — проверка на светлом фоне
pd.rounded_rectangle([286, 226, 446, 284], radius=12, fill=(0xEE, 0xF0, 0xF5))
xs = 300
for s in (32, 16):
    sm = img.resize((s, s), Image.LANCZOS)
    prev.paste(sm, (xs, 255 - s // 2), sm)
    xs += s + 22
pd.text((366, 244), "иконка", font=font(12), fill=(90, 94, 112))
pd.text((366, 258), "на светлом", font=font(12), fill=(90, 94, 112))

prev.save(f"{OUT}_preview.png")
print("icon v3 ok")
