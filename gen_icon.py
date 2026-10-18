"""Генератор иконки grom: фиолетовый градиент, скругления, белая молния."""
from PIL import Image, ImageDraw, ImageFilter

S = 1024
RADIUS = 224

top = (0x8A, 0x7B, 0xFF)   # #8A7BFF
bot = (0x4F, 0x3F, 0xD9)   # #4F3FD9

# ---- вертикальный градиент
grad = Image.new("RGB", (S, S))
d = ImageDraw.Draw(grad)
for y in range(S):
    t = y / (S - 1)
    d.line([(0, y), (S, y)],
           fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))

# ---- мягкое свечение сверху-слева
glow = Image.new("L", (S, S), 0)
gd = ImageDraw.Draw(glow)
gd.ellipse([-260, -320, 760, 520], fill=70)
glow = glow.filter(ImageFilter.GaussianBlur(140))
grad = Image.composite(Image.new("RGB", (S, S), (255, 255, 255)), grad,
                       glow.point(lambda v: int(v * 0.5)))

# ---- молния (белая, с мягким свечением)
bolt = Image.new("L", (S, S), 0)
bd = ImageDraw.Draw(bolt)
points = [(600, 140), (330, 560), (500, 560), (420, 900),
          (710, 470), (545, 470)]
points = [(x - 8, y - 8) for x, y in points]
bd.polygon(points, fill=255)
bolt = bolt.filter(ImageFilter.GaussianBlur(6))

img = grad.convert("RGBA")
white = Image.new("RGBA", (S, S), (255, 255, 255, 255))
img = Image.composite(white, img, bolt)

# ---- скруглённые углы с прозрачностью
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1],
                                       radius=RADIUS, fill=255)
img.putalpha(mask)

# ---- сохранение
img.save("grom_icon.png")
img.save("grom_icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                 (64, 64), (128, 128), (256, 256)])
# превью на тёмном фоне для оценки
prev = Image.new("RGB", (320, 320), (0x0A, 0x0C, 0x10))
prev.paste(img.resize((288, 288), Image.LANCZOS), (16, 16),
           img.resize((288, 288), Image.LANCZOS))
prev.save("grom_icon_preview.png")
print("icon ok")
