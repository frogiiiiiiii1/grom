"""Генератор иконки grom v2.

Диагональный фиолетовый градиент, мягкий блик сверху, диагональная тень
снизу-справа, объёмная молния со скруглёнными углами, свечением и тенью,
тонкий светящийся ободок по внутреннему краю.
"""
import math
from PIL import Image, ImageDraw, ImageFilter

S = 1024
RADIUS = 236

TOP = (0xB2, 0xA6, 0xFF)   # светлый фиолет сверху
BOT = (0x40, 0x30, 0xC6)   # глубокий индиго снизу

# ---- вертикальный градиент
grad = Image.new("RGB", (S, S))
d = ImageDraw.Draw(grad)
for y in range(S):
    t = (y / (S - 1)) ** 0.92
    d.line([(0, y), (S, y)],
           fill=tuple(int(TOP[i] + (BOT[i] - TOP[i]) * t) for i in range(3)))

# ---- тёплый блик сверху-слева
glow = Image.new("L", (S, S), 0)
ImageDraw.Draw(glow).ellipse([-300, -360, 700, 460], fill=95)
glow = glow.filter(ImageFilter.GaussianBlur(150))
grad = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), grad,
                       glow.point(lambda v: int(v * 0.62)))

# ---- стеклянный блик по верхней дуге
gloss = Image.new("L", (S, S), 0)
ImageDraw.Draw(gloss).ellipse([-140, -560, 1164, 380], fill=44)
gloss = gloss.filter(ImageFilter.GaussianBlur(70))
grad = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), grad, gloss)

# ---- диагональная тень снизу-справа
shade = Image.new("L", (S, S), 0)
ImageDraw.Draw(shade).ellipse([380, 380, 1360, 1360], fill=110)
shade = shade.filter(ImageFilter.GaussianBlur(220))
grad = Image.composite(Image.new("RGB", (S, S), (26, 16, 84)), grad,
                       shade.point(lambda v: int(v * 0.72)))

# ---- молния: контур → скругление углов → мягкий край (антиалиас)
POINTS = [(636, 128), (320, 574), (516, 574),
          (396, 896), (716, 452), (540, 452)]
bolt = Image.new("L", (S, S), 0)
ImageDraw.Draw(bolt).polygon(POINTS, fill=255)
bolt = bolt.filter(ImageFilter.GaussianBlur(16))
bolt = bolt.point(lambda v: 255 if v > 127 else 0)   # скруглённые углы
bolt_aa = bolt.filter(ImageFilter.GaussianBlur(2))   # гладкий край

# ---- мягкая тень молнии
shadow = Image.new("L", (S, S), 0)
shadow.paste(bolt, (0, 18))
shadow = shadow.filter(ImageFilter.GaussianBlur(34)).point(
    lambda v: int(v * 0.55))
grad = Image.composite(Image.new("RGB", (S, S), (16, 8, 48)), grad, shadow)

# ---- свечение вокруг молнии
halo = bolt.filter(ImageFilter.GaussianBlur(54)).point(lambda v: int(v * 0.5))
grad = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), grad, halo)

# ---- тело молнии: белый → очень светлый фиолет внизу
bolt_col = Image.new("RGB", (S, S))
bd = ImageDraw.Draw(bolt_col)
for y in range(S):
    t = (y / (S - 1)) ** 1.4
    bd.line([(0, y), (S, y)],
            fill=(255 - int(30 * t), 255 - int(34 * t), 255 - int(4 * t)))
img = Image.composite(bolt_col, grad, bolt_aa)

# ---- тонкий светящийся ободок по внутреннему краю
rim = Image.new("L", (S, S), 0)
ImageDraw.Draw(rim).rounded_rectangle([8, 8, S - 9, S - 9],
                                      radius=RADIUS - 8, outline=255, width=6)
rim = rim.filter(ImageFilter.GaussianBlur(2)).point(lambda v: int(v * 0.40))
img = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), img, rim)

# ---- скруглённые углы с прозрачностью
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1],
                                       radius=RADIUS, fill=255)
img = img.convert("RGBA")
img.putalpha(mask)

# ---- сохранение
img.save("grom_icon.png")
img.save("grom_icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                 (64, 64), (128, 128), (256, 256)])

# превью на тёмном фоне: большой + мелкие размеры (проверка читаемости)
prev = Image.new("RGB", (430, 260), (0x0A, 0x0C, 0x10))
big = img.resize((224, 224), Image.LANCZOS)
prev.paste(big, (24, 18), big)
x = 270
for s in (64, 32, 16):
    small = img.resize((s, s), Image.LANCZOS)
    prev.paste(small, (x, 34), small)
    x += s + 18
prev.save("grom_icon_preview.png")
print("icon ok")
