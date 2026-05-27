"""
Vectra: Production-Grade Synthetic Dataset Generator

Generates 200+ products with programmatically-generated product images
that actually match their descriptions. No external API dependency —
all images are drawn with Pillow to create visually distinct,
category-coherent product representations that produce meaningful
CLIP embeddings.

Usage:
    python scripts/generate_synthetic.py
"""

import os
import csv
import random
import math
from pathlib import Path
from tqdm import tqdm
from PIL import Image, ImageDraw, ImageFilter

OUTPUT_DIR = Path("data/synthetic")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
METADATA_FILE = OUTPUT_DIR / "products.csv"
IMAGES_DIR = OUTPUT_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)

IMG_SIZE = 400
random.seed(42)

COLORS = {
    "White":      (245, 245, 240),
    "Black":      (30,  30,  35),
    "Navy":       (20,  40,  85),
    "Beige":      (225, 210, 185),
    "Olive":      (110, 120, 60),
    "Grey":       (145, 145, 150),
    "Floral":     (210, 110, 160),
    "Sky Blue":   (135, 185, 225),
    "Blue":       (40,  85,  185),
    "Charcoal":   (55,  55,  62),
    "Purple":     (125, 50,  165),
    "Red":        (205, 40,  40),
    "Green":      (50,  155, 55),
    "Khaki":      (180, 170, 125),
    "Brown":      (135, 70,  30),
    "Tan":        (195, 155, 105),
    "Gold":       (215, 175, 40),
    "Silver":     (190, 195, 205),
    "Terracotta": (195, 100, 60),
    "Cream":      (255, 245, 215),
    "Amber":      (205, 145, 35),
    "Orange":     (225, 125, 30),
    "Nude":       (215, 175, 145),
    "Multicolor": (175, 125, 200),
    "Pink":       (225, 125, 185),
    "Teal":       (30,  160, 165),
    "Coral":      (235, 120, 95),
    "Mint":       (100, 200, 150),
    "Lavender":   (180, 140, 210),
    "Burgundy":   (130, 30,  50),
    "Mustard":    (210, 175, 50),
    "Cobalt":     (30,  70,  200),
    "Magenta":    (200, 40,  120),
    "Peach":      (245, 185, 140),
    "Ivory":      (255, 250, 235),
    "Espresso":   (60,  35,  20),
    "Steel":      (110, 120, 130),
    "Blush":      (235, 190, 180),
    "Champagne":  (230, 215, 185),
    "Mauve":      (160, 120, 145),
    "Sage":       (140, 175, 130),
    "Brick":      (180, 70,  50),
}

CATEGORY_BG_COLORS = {
    "Apparel":     (250, 240, 230),
    "Footwear":    (230, 240, 250),
    "Electronics": (235, 230, 250),
    "Home":        (240, 250, 235),
    "Beauty":      (250, 235, 240),
}


def _shadow(im: Image.Image, offset: int = 6, blur: int = 12) -> Image.Image:
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rectangle([offset, offset, im.width-1, im.height-1], fill=(0, 0, 0, 35))
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    out = Image.alpha_composite(shadow, im.convert("RGBA"))
    return out.convert("RGB")


def _rounded_rect(draw, xy, radius, fill):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill)


def _make_bg(category: str = "Apparel") -> tuple[Image.Image, ImageDraw.Draw]:
    base = CATEGORY_BG_COLORS.get(category, (238, 238, 235))
    lighter = tuple(min(c + 25, 255) for c in base)
    img = Image.new("RGB", (IMG_SIZE, IMG_SIZE), base)
    cx = cy = IMG_SIZE // 2

    gradient = Image.new("L", (IMG_SIZE, IMG_SIZE), 0)
    g_draw = ImageDraw.Draw(gradient)
    for r in range(IMG_SIZE // 2, 0, -1):
        alpha = int(180 * (1 - r / (IMG_SIZE // 2)))
        g_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=alpha)

    overlay = Image.new("RGB", (IMG_SIZE, IMG_SIZE), lighter)
    img = Image.composite(overlay, img, gradient)
    return img, ImageDraw.Draw(img)


def _draw_bg_texture(draw: ImageDraw.Draw, product_id: int, category: str):
    rng = random.Random(product_id * 99991)
    pattern = product_id % 7
    c = (min(200, 180 + rng.randint(0, 40)),
         min(200, 180 + rng.randint(0, 40)),
         min(200, 180 + rng.randint(0, 40)))

    if pattern == 0:
        for _ in range(60):
            x = rng.randint(0, IMG_SIZE)
            y = rng.randint(0, IMG_SIZE)
            r = rng.randint(3, 6)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=c, outline=None)
    elif pattern == 1:
        for i in range(0, IMG_SIZE, 30):
            draw.line([(0, i + rng.randint(-5, 5)), (IMG_SIZE, i + rng.randint(-5, 5))], fill=c, width=2)
    elif pattern == 2:
        for i in range(0, IMG_SIZE, 30):
            draw.line([(i + rng.randint(-5, 5), 0), (i + rng.randint(-5, 5), IMG_SIZE)], fill=c, width=2)
    elif pattern == 3:
        for r in range(20, IMG_SIZE, 40):
            draw.ellipse([IMG_SIZE//2 - r, IMG_SIZE//2 - r,
                          IMG_SIZE//2 + r, IMG_SIZE//2 + r], outline=c, width=2)
    elif pattern == 4:
        for i in range(-IMG_SIZE, IMG_SIZE*2, 30):
            offset = rng.randint(-3, 3)
            draw.line([(i, 0), (i + IMG_SIZE, IMG_SIZE)], fill=c, width=2)
    elif pattern == 5:
        r2 = rng.randint(5, 12)
        for x in range(0, IMG_SIZE, r2 * 3):
            for y in range(0, IMG_SIZE, r2 * 3):
                draw.ellipse([x, y, x + r2, y + r2], fill=c)
    else:
        step = rng.randint(25, 45)
        for i in range(0, IMG_SIZE, step):
            draw.line([(i, 0), (i + IMG_SIZE//3, IMG_SIZE)], fill=c, width=1)
            draw.line([(i, IMG_SIZE), (i + IMG_SIZE//3, 0)], fill=c, width=1)


def draw_top(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2 - 10
    w, h = 180, 160
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1 + 25, x1 + w, y1 + h), 40, color)
    draw.rectangle([x1 + 10, y1 + 15, x1 + w - 10, y1 + 30], fill=color)
    neck_r = 25
    draw.ellipse([cx - neck_r, y1 + 5, cx + neck_r, y1 + 5 + neck_r * 2], fill=(250, 250, 248))
    sleeve_y = y1 + 35
    _rounded_rect(draw, (x1 - 30, sleeve_y, x1, sleeve_y + 50), 15, color)
    _rounded_rect(draw, (x1 + w, sleeve_y, x1 + w + 30, sleeve_y + 50), 15, color)
    for i in range(3):
        yy = y1 + h - 30 + i * 12
        draw.line([x1 + 20, yy, x1 + w - 20, yy], fill=(min(color[0]+30, 255), min(color[1]+30, 255), min(color[2]+30, 255)), width=1)
    if sum(color) > 700:
        draw.rounded_rectangle([x1, y1 + 25, x1 + w, y1 + h], radius=40, outline=(180, 180, 180), width=2)


def draw_top_polo(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2 - 10
    w, h = 180, 155
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1 + 25, x1 + w, y1 + h), 35, color)
    draw.rectangle([x1 + 10, y1 + 15, x1 + w - 10, y1 + 30], fill=color)
    collar = [
        (cx - 25, y1 + 20), (cx - 5, y1 + 45), (cx + 5, y1 + 45), (cx + 25, y1 + 20),
        (cx + 15, y1 + 15), (cx - 15, y1 + 15)
    ]
    draw.polygon(collar, fill=(min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255)))
    draw.line([cx - 3, y1 + 40, cx + 3, y1 + 50], fill=(250, 250, 248), width=2)
    sleeve_y = y1 + 35
    _rounded_rect(draw, (x1 - 25, sleeve_y, x1, sleeve_y + 45), 12, color)
    _rounded_rect(draw, (x1 + w, sleeve_y, x1 + w + 25, sleeve_y + 45), 12, color)


def draw_top_hoodie(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 190, 170
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1 + 30, x1 + w, y1 + h), 45, color)
    draw.rectangle([x1 + 10, y1 + 15, x1 + w - 10, y1 + 35], fill=color)
    pocket_y = y1 + h - 55
    _rounded_rect(draw, (x1 + 30, pocket_y, x1 + w - 30, pocket_y + 30), 10, (min(color[0]+25, 255), min(color[1]+25, 255), min(color[2]+25, 255)))
    draw.ellipse([cx - 22, y1 - 10, cx + 22, y1 + 30], fill=color)
    sleeve_y = y1 + 40
    _rounded_rect(draw, (x1 - 35, sleeve_y, x1, sleeve_y + 55), 18, color)
    _rounded_rect(draw, (x1 + w, sleeve_y, x1 + w + 35, sleeve_y + 55), 18, color)


def draw_top_kurti(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2 - 5
    w, h = 175, 175
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1 + 30, x1 + w, y1 + h), 30, color)
    draw.rectangle([x1 + 10, y1 + 15, x1 + w - 10, y1 + 35], fill=color)
    neck = [
        (cx - 20, y1 + 15), (cx, y1 + 35), (cx + 20, y1 + 15),
        (cx + 10, y1 + 8), (cx - 10, y1 + 8)
    ]
    draw.polygon(neck, fill=(250, 250, 248))
    for i in range(4):
        yy = y1 + h - 40 + i * 12
        draw.line([x1 + 25, yy, x1 + w - 25, yy], fill=(245, 235, 220), width=1)


def draw_bottoms(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2 + 10
    w, h = 140, 170
    x1, y1 = cx - w // 2, cy - h // 2
    leg_w = 55
    gap = 10
    lx1 = cx - leg_w - gap // 2
    lx2 = cx + gap // 2
    _rounded_rect(draw, (lx1, y1, lx1 + leg_w, y1 + h), 20, color)
    _rounded_rect(draw, (lx2, y1, lx2 + leg_w, y1 + h), 20, color)
    waist_y = y1 - 5
    draw.rectangle([lx1 - 5, waist_y, lx2 + leg_w + 5, waist_y + 15], fill=color)
    for i in range(2):
        yy = waist_y + 25 + i * 50
        fold = (min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255))
        draw.line([lx1 + 10, yy, lx1 + leg_w - 10, yy], fill=fold, width=1)
        draw.line([lx2 + 10, yy, lx2 + leg_w - 10, yy], fill=fold, width=1)


def draw_shorts(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2 + 15
    w, h = 150, 100
    x1, y1 = cx - w // 2, cy - h // 2
    leg_w = 60
    gap = 10
    lx1 = cx - leg_w - gap // 2
    lx2 = cx + gap // 2
    _rounded_rect(draw, (lx1, y1, lx1 + leg_w, y1 + h), 20, color)
    _rounded_rect(draw, (lx2, y1, lx2 + leg_w, y1 + h), 20, color)
    waist_y = y1 - 5
    draw.rectangle([lx1 - 5, waist_y, lx2 + leg_w + 5, waist_y + 15], fill=color)


def draw_leggings(draw, color):
    draw_bottoms(draw, color)


def draw_dress(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    top_w, bot_w, h = 100, 240, 200
    x1, y1 = cx - top_w // 2, cy - h // 2
    points = [
        (x1, y1 + 40), (x1 + top_w, y1 + 40),
        (x1 + bot_w, y1 + h), (x1, y1 + h)
    ]
    draw.polygon(points, fill=color)
    draw.rectangle([x1 + 10, y1 + 10, x1 + top_w - 10, y1 + 40], fill=color)
    neck_r = 22
    draw.ellipse([cx - neck_r, y1, cx + neck_r, y1 + neck_r * 1.5], fill=(250, 250, 248))
    dots_y = y1 + h - 50
    for dx in range(0, bot_w - 40, 25):
        draw.ellipse([x1 + 30 + dx, dots_y, x1 + 40 + dx, dots_y + 10], fill=(240, 230, 220))


def draw_outerwear(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 200, 175
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1 + 30, x1 + w, y1 + h), 50, color)
    draw.rectangle([x1 + 10, y1 + 15, x1 + w - 10, y1 + 35], fill=color)
    lapel_l = [(x1 + 5, y1 + 25), (cx - 5, y1 + 70), (cx - 3, y1 + 30)]
    lapel_r = [(x1 + w - 5, y1 + 25), (cx + 5, y1 + 70), (cx + 3, y1 + 30)]
    lighter = (min(color[0]+35, 255), min(color[1]+35, 255), min(color[2]+35, 255))
    draw.polygon(lapel_l, fill=lighter)
    draw.polygon(lapel_r, fill=lighter)
    button_ys = [y1 + 80, y1 + 110, y1 + 140]
    for by in button_ys:
        draw.ellipse([cx - 4, by - 4, cx + 4, by + 4], fill=(50, 50, 50))
    sleeve_y = y1 + 45
    _rounded_rect(draw, (x1 - 35, sleeve_y, x1, sleeve_y + 65), 20, color)
    _rounded_rect(draw, (x1 + w, sleeve_y, x1 + w + 35, sleeve_y + 65), 20, color)


def draw_shoe(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 200, 100
    x1, y1 = cx - w // 2, cy - h // 2
    draw.pieslice([x1 - 20, y1, x1 + 60, y1 + h], 270, 90, fill=color)
    draw.rectangle([x1 + 30, y1, x1 + w - 40, y1 + h], fill=color)
    draw.pieslice([x1 + w - 80, y1, x1 + w - 10, y1 + h], 90, 270, fill=color)
    draw.ellipse([x1 + 50, y1 + 35, x1 + 80, y1 + 65], fill=(min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255)))
    draw.arc([x1 - 10, y1 + 5, x1 + 50, y1 + h - 5], 200, 340, fill=(50, 50, 50), width=3)
    sole = min(color[0]-20, 0) if color[0] > 20 else (min(color[0]+40, 255))
    draw.rectangle([x1 + 10, y1 + h - 8, x1 + w - 30, y1 + h], fill=(60, 60, 60))


def draw_sandal(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 180, 70
    x1, y1 = cx - w // 2, cy - h // 2
    draw.ellipse([x1, y1 + 20, x1 + w, y1 + h - 10], fill=(60, 60, 60))
    strap_color = (min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255))
    draw.arc([x1 + 20, y1 - 5, x1 + 100, y1 + 40], 200, 340, fill=strap_color, width=5)
    draw.arc([x1 + 60, y1 - 5, x1 + 140, y1 + 40], 200, 340, fill=strap_color, width=5)
    draw.ellipse([cx - 8, y1 + 20, cx + 8, y1 + 36], fill=strap_color)
    draw.ellipse([x1 + 35, y1 + 25, x1 + 45, y1 + 35], fill=strap_color)
    draw.ellipse([x1 + w - 45, y1 + 25, x1 + w - 35, y1 + 35], fill=strap_color)


def draw_boot(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 180, 200
    x1, y1 = cx - w // 2, cy - h // 2
    draw.rectangle([x1 + 30, y1 - 5, x1 + w - 30, y1 + h - 40], fill=color)
    draw.pieslice([x1 - 10, y1 + h - 80, x1 + w - 20, y1 + h], 180, 360, fill=color)
    draw.rectangle([x1 - 10, y1 + h - 40, x1 + w - 20, y1 + h], fill=(60, 60, 60))
    for i in range(4):
        yy = y1 + 30 + i * 30
        draw.line([x1 + 40, yy, x1 + w - 40, yy], fill=(min(color[0]+25, 255), min(color[1]+25, 255), min(color[2]+25, 255)), width=2)


def draw_sneaker(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 200, 100
    x1, y1 = cx - w // 2, cy - h // 2
    draw.pieslice([x1 - 15, y1 + 5, x1 + 55, y1 + h - 5], 270, 90, fill=color)
    draw.rectangle([x1 + 25, y1 + 5, x1 + w - 35, y1 + h - 5], fill=color)
    draw.pieslice([x1 + w - 75, y1 + 5, x1 + w - 10, y1 + h - 5], 90, 270, fill=color)
    laces_y = y1 + 20
    for i in range(4):
        lx = x1 + 45 + i * 12
        draw.line([lx, laces_y, lx + 6, laces_y + 12], fill=(255, 255, 255), width=2)
    draw.ellipse([x1 + 40, y1 + 45, x1 + 60, y1 + 65], fill=(200, 200, 200))
    sole_color = (min(color[0]-30, 200)) if color[0] > 50 else (80, 80, 80)
    draw.rectangle([x1 + 15, y1 + h - 10, x1 + w - 25, y1 + h], fill=sole_color)
    swoosh = [(x1 + 80, y1 + 40), (x1 + 140, y1 + 30), (x1 + 150, y1 + 45), (x1 + 130, y1 + 40)]
    draw.polygon(swoosh, fill=(255, 255, 255))


def draw_earbuds(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    draw.ellipse([cx - 55, cy - 25, cx - 15, cy + 35], fill=color)
    draw.ellipse([cx + 15, cy - 25, cx + 55, cy + 35], fill=color)
    draw.ellipse([cx - 45, cy - 15, cx - 25, cy + 25], fill=(min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255)))
    draw.ellipse([cx + 25, cy - 15, cx + 45, cy + 25], fill=(min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255)))
    draw.rectangle([cx - 10, cy - 5, cx + 10, cy + 15], fill=color)


def draw_watch(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    band_color = (min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255))
    draw.rectangle([cx - 15, cy - 90, cx + 15, cy - 30], fill=band_color)
    draw.rectangle([cx - 15, cy + 30, cx + 15, cy + 90], fill=band_color)
    face_r = 50
    draw.ellipse([cx - face_r, cy - face_r, cx + face_r, cy + face_r], fill=(20, 20, 25))
    draw.ellipse([cx - face_r + 5, cy - face_r + 5, cx + face_r - 5, cy + face_r - 5], fill=color)
    draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], fill=(200, 200, 200))
    for angle in [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]:
        rad = math.radians(angle - 90)
        mx = cx + int(35 * math.cos(rad))
        my = cy + int(35 * math.sin(rad))
        draw.line([cx, cy, mx, my], fill=(200, 200, 200), width=1)
    draw.arc([cx - 45, cy - 45, cx + 45, cy + 45], 0, 360, fill=(150, 150, 150), width=3)


def draw_speaker(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 160, 120
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 20, color)
    draw.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=(min(color[0]-15, 30), min(color[1]-15, 30), min(color[2]-15, 30)))
    for r in [15, 25]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(150, 150, 150), width=1)
    for i in range(4):
        dx = -45 + i * 12
        draw.rectangle([cx + dx, y1 + h - 20, cx + dx + 6, y1 + h - 8], fill=(50, 50, 50))


def draw_keyboard(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 240, 90
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 12, color)
    key_w, key_h = 14, 12
    gap = 4
    for row in range(4):
        for col in range(12):
            kx = x1 + 10 + col * (key_w + gap)
            ky = y1 + 8 + row * (key_h + gap)
            if row == 3 and col > 9:
                continue
            _rounded_rect(draw, (kx, ky, kx + key_w, ky + key_h), 3, (min(color[0]+30, 255), min(color[1]+30, 255), min(color[2]+30, 255)))
    space_x = x1 + 40
    _rounded_rect(draw, (space_x, y1 + h - key_h - 8, space_x + 100, y1 + h - 8), 3, (min(color[0]+30, 255), min(color[1]+30, 255), min(color[2]+30, 255)))


def draw_mouse(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    draw.ellipse([cx - 50, cy - 70, cx + 50, cy + 60], fill=color)
    draw.line([cx, cy - 50, cx, cy + 30], fill=(min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255)), width=2)
    draw.ellipse([cx - 20, cy - 55, cx + 20, cy - 25], fill=(min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255)))
    draw.ellipse([cx - 3, cy + 35, cx + 3, cy + 45], fill=(100, 100, 100))
    draw.line([cx - 45, cy - 65, cx + 45, cy - 65], fill=(min(color[0]+25, 255), min(color[1]+25, 255), min(color[2]+25, 255)), width=1)


def draw_headphones(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    # band as arc directly on main image
    draw.arc([cx - 120, cy - 100, cx + 120, cy + 60], 200, 340, fill=color, width=14)
    draw.ellipse([cx - 90, cy + 10, cx - 30, cy + 80], fill=color)
    draw.ellipse([cx + 30, cy + 10, cx + 90, cy + 80], fill=color)
    cushion_color = (min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255))
    draw.ellipse([cx - 85, cy + 15, cx - 35, cy + 75], fill=cushion_color)
    draw.ellipse([cx + 35, cy + 15, cx + 85, cy + 75], fill=cushion_color)


def draw_small_rect(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 140, 80
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 15, color)
    lighter = (min(color[0]+35, 255), min(color[1]+35, 255), min(color[2]+35, 255))
    _rounded_rect(draw, (x1 + 15, y1 + 10, x1 + w - 15, y1 + h - 10), 8, lighter)
    for i in range(3):
        draw.ellipse([x1 + 25 + i * 20, y1 + h - 20, x1 + 33 + i * 20, y1 + h - 12], fill=(50, 50, 50))


def draw_tv(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 260, 170
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 8, color)
    sx1, sy1 = x1 + 10, y1 + 12
    draw.rectangle([sx1, sy1, x1 + w - 10, y1 + h - 12], fill=(20, 25, 40))
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        sx = sx1 + (w - 20) // 2 + int(40 * math.cos(rad))
        sy = sy1 + (h - 24) // 2 + int(25 * math.sin(rad))
        draw.ellipse([sx - 10, sy - 10, sx + 10, sy + 10], fill=(50, 80, 140))
    stand_y = y1 + h - 5
    draw.polygon([(cx - 30, stand_y), (cx + 30, stand_y), (cx + 20, stand_y + 20), (cx - 20, stand_y + 20)], fill=(80, 80, 80))
    draw.rectangle([cx - 8, stand_y + 20, cx + 8, stand_y + 30], fill=(80, 80, 80))


def draw_camera(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 200, 140
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 15, color)
    _rounded_rect(draw, (x1 + 20, y1 - 10, x1 + 60, y1 + 15), 5, (min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255)))
    lens_r = 40
    draw.ellipse([cx - lens_r, cy - lens_r, cx + lens_r, cy + lens_r], fill=(30, 30, 35))
    draw.ellipse([cx - lens_r + 5, cy - lens_r + 5, cx + lens_r - 5, cy + lens_r - 5], fill=(60, 60, 65))
    draw.ellipse([cx - 15, cy - 15, cx + 15, cy + 15], fill=(100, 100, 120))
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(40, 50, 80))


def draw_reader(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 160, 220
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 10, color)
    sx1, sy1 = x1 + 15, y1 + 20
    draw.rectangle([sx1, sy1, x1 + w - 15, y1 + h - 20], fill=(180, 175, 160))
    for line_y in range(sy1 + 10, sy1 + h - 50, 20):
        draw.line([(sx1 + 20, line_y), (x1 + w - 35, line_y)], fill=(160, 155, 140), width=2)
    draw.ellipse([x1 + w // 2 - 5, y1 + h - 18, x1 + w // 2 + 5, y1 + h - 8], fill=(80, 80, 80))


def draw_bulb(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2 - 10
    # Bulb glass
    draw.ellipse([cx - 55, cy - 55, cx + 55, cy + 45], fill=(230, 230, 220))
    glow = (min(color[0]+60, 255), min(color[1]+60, 255), min(color[2]+60, 255))
    draw.ellipse([cx - 35, cy - 35, cx + 35, cy + 25], fill=glow)
    draw.ellipse([cx - 12, cy - 12, cx + 12, cy + 8], fill=(250, 250, 200))
    # Base
    base_w = 30
    base_h = 30
    bx1, by1 = cx - base_w // 2, cy + 35
    draw.rectangle([bx1, by1, bx1 + base_w, by1 + base_h], fill=color)
    for i in range(3):
        draw.line([bx1 + 2, by1 + 5 + i * 8, bx1 + base_w - 2, by1 + 5 + i * 8], fill=(min(color[0]+30, 255), min(color[1]+30, 255), min(color[2]+30, 255)), width=1)
    # Screw
    draw.rectangle([bx1 + 3, by1 + base_h, bx1 + base_w - 3, by1 + base_h + 10], fill=(60, 60, 60))


def draw_mug(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 130, 150
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1 + 5, x1 + w, y1 + h), 10, color)
    draw.ellipse([x1, y1, x1 + w, y1 + 20], fill=(min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255)))
    handle = [
        (x1 + w - 5, y1 + 35),
        (x1 + w + 35, y1 + 35),
        (x1 + w + 35, y1 + 95),
        (x1 + w - 5, y1 + 95),
    ]
    draw.arc([x1 + w - 10, y1 + 30, x1 + w + 40, y1 + 100], 270, 90, fill=color, width=12)
    draw.ellipse([x1 + w - 50, y1 + 40, x1 + w - 20, y1 + 100], fill=(180, 150, 120))


def draw_candle(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 120, 170
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 15, color)
    draw.ellipse([x1, y1 - 5, x1 + w, y1 + 10], fill=(min(color[0]+25, 255), min(color[1]+25, 255), min(color[2]+25, 255)))
    lighter = (min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255))
    _rounded_rect(draw, (x1 + 15, y1 + 30, x1 + w - 15, y1 + h - 20), 8, lighter)
    flame_y = y1 - 20
    draw.ellipse([cx - 8, flame_y - 20, cx + 8, flame_y + 10], fill=(255, 200, 50))
    draw.ellipse([cx - 4, flame_y - 12, cx + 4, flame_y + 2], fill=(255, 255, 200))
    for i in range(2):
        y_wick = y1 - 5 + i * 3
        draw.line([cx, y1 - 5, cx, flame_y + 5], fill=(80, 80, 80), width=2)


def draw_blanket(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 240, 160
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 15, color)
    fold_y = y1 + h // 3
    lighter = (min(color[0]+25, 255), min(color[1]+25, 255), min(color[2]+25, 255))
    _rounded_rect(draw, (x1 + 10, fold_y, x1 + w - 10, fold_y + 15), 5, lighter)
    _rounded_rect(draw, (x1 + 10, fold_y + 35, x1 + w - 10, fold_y + 50), 5, lighter)
    for i in range(4):
        yy = y1 + 20 + i * 30
        draw.line([x1 + 30, yy, x1 + w - 30, yy], fill=(lighter[0], lighter[1], lighter[2]), width=1)


def draw_tray(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 260, 160
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 30, color)
    inner = (min(color[0]+30, 255), min(color[1]+30, 255), min(color[2]+30, 255))
    _rounded_rect(draw, (x1 + 15, y1 + 15, x1 + w - 15, y1 + h - 15), 20, inner)
    draw.ellipse([cx - 40, cy - 15, cx + 40, cy + 15], fill=(min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255)))


def draw_bottle(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 80, 220
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1 + 10, y1 + 60, x1 + w - 10, y1 + h), 12, color)
    neck_w = 30
    nx1 = cx - neck_w // 2
    draw.rectangle([nx1, y1 + 15, nx1 + neck_w, y1 + 65], fill=color)
    cap = (min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255))
    _rounded_rect(draw, (nx1 - 2, y1, nx1 + neck_w + 2, y1 + 20), 5, cap)
    label = (min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255))
    _rounded_rect(draw, (x1 + 5, y1 + 90, x1 + w - 5, y1 + 150), 5, label)
    if color == (245, 245, 240):
        draw.line([cx - 15, y1 + 100, cx + 15, y1 + 100], fill=(200, 200, 200), width=2)


def draw_plant_pot(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2 + 20
    pot_t, pot_b, h = 80, 140, 120
    x1 = cx - pot_t // 2
    x2 = cx - pot_b // 2
    y1 = cy - h // 2
    terracotta = (195, 100, 60)
    pot_color = terracotta if color == terracotta else color
    draw.polygon([(x1, y1), (x1 + pot_t, y1), (x1 + pot_b, y1 + h), (x1, y1 + h)], fill=pot_color)
    rim_w = pot_t + 10
    rim_color = terracotta if color == terracotta else (min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255))
    _rounded_rect(draw, (cx - rim_w // 2, y1 - 5, cx + rim_w // 2, y1 + 8), 5, rim_color)
    for leaf_x in [cx - 30, cx - 15, cx, cx + 15, cx + 30]:
        lx = leaf_x
        ly = y1 - 5
        draw.pieslice([lx - 20, ly - 40, lx, ly], 180, 360, fill=(60, 140, 60))
        draw.pieslice([lx, ly - 40, lx + 20, ly], 0, 180, fill=(70, 160, 70))


def draw_organiser(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 200, 120
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 10, color)
    divider_x = cx
    lighter = (min(color[0]+30, 255), min(color[1]+30, 255), min(color[2]+30, 255))
    draw.rectangle([divider_x - 3, y1 + 5, divider_x + 3, y1 + h - 5], fill=color)
    _rounded_rect(draw, (x1 + 10, y1 + 10, divider_x - 5, y1 + h - 10), 5, lighter)
    _rounded_rect(draw, (divider_x + 5, y1 + 10, x1 + w - 10, y1 + h - 10), 5, lighter)


def draw_towel(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 240, 140
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 10, color)
    fold_y = y1 + h // 3
    for i in range(3):
        yy = fold_y + i * 25
        draw.line([x1 + 15, yy, x1 + w - 15, yy], fill=(min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255)), width=2)
    stripe = (min(color[0]+30, 255), min(color[1]+30, 255), min(color[2]+30, 255))
    _rounded_rect(draw, (x1 + 20, y1 + h - 25, x1 + w - 20, y1 + h - 8), 3, stripe)


def draw_frame(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    size = 180
    x1, y1 = cx - size // 2, cy - size // 2
    border = 15
    draw.rectangle([x1, y1, x1 + size, y1 + size], fill=color)
    inner = (min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255))
    draw.rectangle([x1 + border, y1 + border, x1 + size - border, y1 + size - border], fill=(240, 235, 225))
    draw.rectangle([x1 + border + 5, y1 + border + 5, x1 + size - border - 5, y1 + size - border - 5], fill=(200, 200, 200))
    s_draw = ImageDraw.Draw(Image.new("RGB", (size - 2 * border - 10, size - 2 * border - 10), (0, 0, 0)))
    d_x, d_y = x1 + border + 5, y1 + border + 5
    for angle in range(0, 150, 30):
        rad = math.radians(angle)
        px = 10 + (size // 3) * math.cos(rad)
        py = 10 + (size // 3) * math.sin(rad)
        draw.ellipse([d_x + px - 3, d_y + py - 3, d_x + px + 3, d_y + py + 3], fill=(180, 150, 100))


def draw_purifier(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 140, 200
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 15, color)
    vent = (min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255))
    _rounded_rect(draw, (x1 + 15, y1 + 30, x1 + w - 15, y1 + 80), 8, vent)
    for i in range(6):
        vx = x1 + 22 + i * 16
        draw.line([vx, y1 + 35, vx, y1 + 75], fill=(min(color[0]+15, 255), min(color[1]+15, 255), min(color[2]+15, 255)), width=2)
    draw.ellipse([cx - 20, y1 + 100, cx + 20, y1 + 140], fill=(50, 50, 55))
    draw.ellipse([cx - 8, y1 + 115, cx + 8, y1 + 125], fill=(100, 200, 255))
    for i in range(3):
        button_y = y1 + h - 35 + i * 12
        draw.ellipse([cx - 5, button_y, cx + 5, button_y + 10], fill=(min(color[0]+50, 255), min(color[1]+50, 255), min(color[2]+50, 255)))


def draw_vacuum(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    r = 100
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    inner_r = r - 15
    draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], fill=(min(color[0]+15, 255), min(color[1]+15, 255), min(color[2]+15, 255)))
    draw.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=(50, 50, 55))
    draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(100, 200, 100))
    for angle in [0, 45, 90, 135, 180, 225, 270, 315]:
        rad = math.radians(angle)
        sx = cx + int(70 * math.cos(rad))
        sy = cy + int(70 * math.sin(rad))
        draw.line([cx, cy, sx, sy], fill=(min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255)), width=2)


def draw_lipstick(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2 + 10
    w, h = 50, 160
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1 + 60, x1 + w, y1 + h), 8, (60, 60, 65))
    draw.polygon([(x1 - 5, y1 + 60), (x1 + w + 5, y1 + 60), (x1 + w - 5, y1 + 25), (x1 + 5, y1 + 25)], fill=color)
    draw.ellipse([x1 + 5, y1 + 18, x1 + w - 5, y1 + 35], fill=color)
    band = (min(color[0]+30, 255), min(color[1]+30, 255), min(color[2]+30, 255))
    draw.rectangle([x1 - 3, y1 + 55, x1 + w + 3, y1 + 62], fill=band)


def draw_palette(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 220, 150
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1, x1 + w, y1 + h), 15, color)
    draw.ellipse([x1 + 10, y1 + 10, x1 + 40, y1 + 40], fill=(220, 60, 60))
    draw.ellipse([x1 + 50, y1 + 10, x1 + 80, y1 + 40], fill=(60, 180, 60))
    draw.ellipse([x1 + 90, y1 + 10, x1 + 120, y1 + 40], fill=(60, 60, 200))
    draw.ellipse([x1 + 130, y1 + 10, x1 + 160, y1 + 40], fill=(220, 200, 40))
    draw.ellipse([x1 + 170, y1 + 10, x1 + 200, y1 + 40], fill=(160, 60, 160))
    draw.ellipse([x1 + 30, y1 + 55, x1 + 60, y1 + 85], fill=(220, 140, 40))
    draw.ellipse([x1 + 80, y1 + 55, x1 + 110, y1 + 85], fill=(60, 200, 200))
    draw.ellipse([x1 + 130, y1 + 55, x1 + 160, y1 + 85], fill=(200, 60, 120))
    draw.ellipse([x1 + 50, y1 + 100, x1 + 80, y1 + 130], fill=(100, 60, 160))
    draw.ellipse([x1 + 130, y1 + 100, x1 + 160, y1 + 130], fill=(220, 100, 40))
    brush = (min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255))
    _rounded_rect(draw, (x1 + w - 35, y1 + 5, x1 + w - 8, y1 + h - 5), 5, brush)


def draw_tube(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 90, 190
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1 + 40, x1 + w, y1 + h), 20, color)
    cap = (min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255))
    _rounded_rect(draw, (x1 + 20, y1 + 15, x1 + w - 20, y1 + 45), 5, cap)
    draw.ellipse([x1 + 28, y1 + 5, x1 + w - 28, y1 + 20], fill=(150, 150, 150))
    band = (min(color[0]+25, 255), min(color[1]+25, 255), min(color[2]+25, 255))
    draw.rectangle([x1 + 5, y1 + h - 30, x1 + w - 5, y1 + h - 10], fill=band)


def draw_perfume(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 80, 220
    x1, y1 = cx - w // 2, cy - h // 2
    draw.rectangle([x1 + 5, y1 + 60, x1 + w - 5, y1 + h], fill=(200, 195, 185))
    draw.rectangle([x1 + 10, y1 + 60, x1 + w - 10, y1 + h], fill=color)
    neck_w = 24
    nx1 = cx - neck_w // 2
    draw.rectangle([nx1, y1 + 30, nx1 + neck_w, y1 + 65], fill=(180, 175, 165))
    cap_h = 35
    _rounded_rect(draw, (nx1 - 5, y1 - 5, nx1 + neck_w + 5, y1 + cap_h), 5, (60, 60, 65))
    accent = (min(color[0]+35, 255), min(color[1]+35, 255), min(color[2]+35, 255))
    draw.rectangle([x1 + 15, y1 + 90, x1 + w - 15, y1 + 110], fill=accent)
    draw.ellipse([cx - 12, y1 + 140, cx + 12, y1 + 160], fill=accent)


def draw_dropper(draw, color):
    cx, cy = IMG_SIZE // 2, IMG_SIZE // 2
    w, h = 70, 220
    x1, y1 = cx - w // 2, cy - h // 2
    _rounded_rect(draw, (x1, y1 + 50, x1 + w, y1 + h), 15, color)
    cap = (min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255))
    _rounded_rect(draw, (x1 + 12, y1 + 25, x1 + w - 12, y1 + 55), 5, cap)
    bulb = (min(color[0]+40, 255), min(color[1]+40, 255), min(color[2]+40, 255))
    draw.ellipse([cx - 12, y1 + 8, cx + 12, y1 + 30], fill=bulb)
    label = (min(color[0]+35, 255), min(color[1]+35, 255), min(color[2]+35, 255))
    _rounded_rect(draw, (x1 + 5, y1 + 80, x1 + w - 5, y1 + 130), 5, label)
    draw.line([cx - 15, y1 + 95, cx + 15, y1 + 95], fill=(min(color[0]+20, 255), min(color[1]+20, 255), min(color[2]+20, 255)), width=2)


def draw_hair_oil(draw, color):
    draw_bottle(draw, color)


PRODUCTS = [
    # ── APPAREL ── (40 products)
    {"name": "Classic Cotton T-Shirt", "category": "Apparel", "subcategory": "Tops", "color": "White", "price": 499, "in_stock": True, "draw_fn": draw_top},
    {"name": "Classic Cotton T-Shirt", "category": "Apparel", "subcategory": "Tops", "color": "Black", "price": 499, "in_stock": True, "draw_fn": draw_top},
    {"name": "Classic Cotton T-Shirt", "category": "Apparel", "subcategory": "Tops", "color": "Navy", "price": 499, "in_stock": False, "draw_fn": draw_top},
    {"name": "Slim Fit Chinos", "category": "Apparel", "subcategory": "Bottoms", "color": "Beige", "price": 1299, "in_stock": True, "draw_fn": draw_bottoms},
    {"name": "Slim Fit Chinos", "category": "Apparel", "subcategory": "Bottoms", "color": "Olive", "price": 1299, "in_stock": True, "draw_fn": draw_bottoms},
    {"name": "Slim Fit Chinos", "category": "Apparel", "subcategory": "Bottoms", "color": "Grey", "price": 1299, "in_stock": True, "draw_fn": draw_bottoms},
    {"name": "Floral Summer Dress", "category": "Apparel", "subcategory": "Dresses", "color": "Floral", "price": 1599, "in_stock": True, "draw_fn": draw_dress},
    {"name": "Linen Shirt", "category": "Apparel", "subcategory": "Tops", "color": "Sky Blue", "price": 899, "in_stock": True, "draw_fn": draw_top},
    {"name": "Linen Shirt", "category": "Apparel", "subcategory": "Tops", "color": "White", "price": 899, "in_stock": True, "draw_fn": draw_top_polo},
    {"name": "Denim Jacket", "category": "Apparel", "subcategory": "Outerwear", "color": "Blue", "price": 2499, "in_stock": True, "draw_fn": draw_outerwear},
    {"name": "Hoodie Sweatshirt", "category": "Apparel", "subcategory": "Tops", "color": "Grey", "price": 1199, "in_stock": True, "draw_fn": draw_top_hoodie},
    {"name": "Formal Blazer", "category": "Apparel", "subcategory": "Outerwear", "color": "Charcoal", "price": 3499, "in_stock": True, "draw_fn": draw_outerwear},
    {"name": "Yoga Leggings", "category": "Apparel", "subcategory": "Activewear", "color": "Black", "price": 799, "in_stock": True, "draw_fn": draw_leggings},
    {"name": "Yoga Leggings", "category": "Apparel", "subcategory": "Activewear", "color": "Purple", "price": 799, "in_stock": False, "draw_fn": draw_leggings},
    {"name": "Kurti Ethnic Wear", "category": "Apparel", "subcategory": "Ethnic", "color": "Red", "price": 1099, "in_stock": True, "draw_fn": draw_top_kurti},
    {"name": "Polo Shirt", "category": "Apparel", "subcategory": "Tops", "color": "Green", "price": 699, "in_stock": True, "draw_fn": draw_top_polo},
    {"name": "Cargo Shorts", "category": "Apparel", "subcategory": "Bottoms", "color": "Khaki", "price": 899, "in_stock": True, "draw_fn": draw_shorts},
    {"name": "Winter Puffer Jacket", "category": "Apparel", "subcategory": "Outerwear", "color": "Red", "price": 3999, "in_stock": True, "draw_fn": draw_outerwear},
    {"name": "Silk Evening Gown", "category": "Apparel", "subcategory": "Dresses", "color": "Burgundy", "price": 4999, "in_stock": True, "draw_fn": draw_dress},
    {"name": "Cotton Pyjama Set", "category": "Apparel", "subcategory": "Bottoms", "color": "Mint", "price": 899, "in_stock": True, "draw_fn": draw_bottoms},
    {"name": "Casual Blazer", "category": "Apparel", "subcategory": "Outerwear", "color": "Navy", "price": 2999, "in_stock": True, "draw_fn": draw_outerwear},
    {"name": "Graphic T-Shirt", "category": "Apparel", "subcategory": "Tops", "color": "White", "price": 599, "in_stock": True, "draw_fn": draw_top_polo},
    {"name": "Graphic T-Shirt", "category": "Apparel", "subcategory": "Tops", "color": "Black", "price": 599, "in_stock": True, "draw_fn": draw_top},
    {"name": "Pleated Skirt", "category": "Apparel", "subcategory": "Bottoms", "color": "Navy", "price": 1199, "in_stock": True, "draw_fn": draw_bottoms},
    {"name": "Denim Shorts", "category": "Apparel", "subcategory": "Bottoms", "color": "Blue", "price": 699, "in_stock": True, "draw_fn": draw_shorts},
    {"name": "Striped Polo", "category": "Apparel", "subcategory": "Tops", "color": "White", "price": 899, "in_stock": True, "draw_fn": draw_top_polo},
    {"name": "Striped Polo", "category": "Apparel", "subcategory": "Tops", "color": "Navy", "price": 899, "in_stock": True, "draw_fn": draw_top_polo},
    {"name": "Summer Tank Top", "category": "Apparel", "subcategory": "Tops", "color": "Coral", "price": 349, "in_stock": True, "draw_fn": draw_top},
    {"name": "Cardigan Sweater", "category": "Apparel", "subcategory": "Outerwear", "color": "Beige", "price": 1999, "in_stock": True, "draw_fn": draw_outerwear},
    {"name": "Jogger Sweatpants", "category": "Apparel", "subcategory": "Bottoms", "color": "Grey", "price": 999, "in_stock": True, "draw_fn": draw_bottoms},
    {"name": "Jogger Sweatpants", "category": "Apparel", "subcategory": "Bottoms", "color": "Black", "price": 999, "in_stock": True, "draw_fn": draw_bottoms},
    {"name": "Tunic Top", "category": "Apparel", "subcategory": "Tops", "color": "Teal", "price": 799, "in_stock": True, "draw_fn": draw_top_kurti},
    {"name": "Leather Jacket", "category": "Apparel", "subcategory": "Outerwear", "color": "Black", "price": 5999, "in_stock": True, "draw_fn": draw_outerwear},
    {"name": "Denim Skirt", "category": "Apparel", "subcategory": "Bottoms", "color": "Blue", "price": 999, "in_stock": True, "draw_fn": draw_bottoms},
    {"name": "Linen Trousers", "category": "Apparel", "subcategory": "Bottoms", "color": "Cream", "price": 1499, "in_stock": True, "draw_fn": draw_bottoms},
    {"name": "Cropped Hoodie", "category": "Apparel", "subcategory": "Tops", "color": "Pink", "price": 1299, "in_stock": True, "draw_fn": draw_top_hoodie},
    {"name": "Slim Fit Chinos", "category": "Apparel", "subcategory": "Bottoms", "color": "Navy", "price": 1299, "in_stock": True, "draw_fn": draw_bottoms},
    {"name": "Knit Sweater", "category": "Apparel", "subcategory": "Tops", "color": "Burgundy", "price": 1599, "in_stock": True, "draw_fn": draw_top},
    {"name": "Knit Sweater", "category": "Apparel", "subcategory": "Tops", "color": "Cream", "price": 1599, "in_stock": True, "draw_fn": draw_top},
    {"name": "Windbreaker Jacket", "category": "Apparel", "subcategory": "Outerwear", "color": "Teal", "price": 2499, "in_stock": True, "draw_fn": draw_outerwear},

    # ── FOOTWEAR ── (25 products)
    {"name": "Running Sneakers", "category": "Footwear", "subcategory": "Sports", "color": "White", "price": 2999, "in_stock": True, "draw_fn": draw_sneaker},
    {"name": "Running Sneakers", "category": "Footwear", "subcategory": "Sports", "color": "Black", "price": 2999, "in_stock": True, "draw_fn": draw_sneaker},
    {"name": "Running Sneakers", "category": "Footwear", "subcategory": "Sports", "color": "Red", "price": 2999, "in_stock": False, "draw_fn": draw_sneaker},
    {"name": "Leather Oxford Shoes", "category": "Footwear", "subcategory": "Formal", "color": "Brown", "price": 3499, "in_stock": True, "draw_fn": draw_shoe},
    {"name": "Leather Oxford Shoes", "category": "Footwear", "subcategory": "Formal", "color": "Black", "price": 3499, "in_stock": True, "draw_fn": draw_shoe},
    {"name": "Casual Loafers", "category": "Footwear", "subcategory": "Casual", "color": "Tan", "price": 1799, "in_stock": True, "draw_fn": draw_shoe},
    {"name": "Flip Flops", "category": "Footwear", "subcategory": "Casual", "color": "Blue", "price": 299, "in_stock": True, "draw_fn": draw_sandal},
    {"name": "High Heel Sandals", "category": "Footwear", "subcategory": "Heels", "color": "Gold", "price": 2199, "in_stock": True, "draw_fn": draw_sandal},
    {"name": "Canvas Sneakers", "category": "Footwear", "subcategory": "Casual", "color": "White", "price": 999, "in_stock": True, "draw_fn": draw_sneaker},
    {"name": "Canvas Sneakers", "category": "Footwear", "subcategory": "Casual", "color": "Navy", "price": 999, "in_stock": True, "draw_fn": draw_sneaker},
    {"name": "Ankle Boots", "category": "Footwear", "subcategory": "Boots", "color": "Black", "price": 3999, "in_stock": True, "draw_fn": draw_boot},
    {"name": "Sports Sandals", "category": "Footwear", "subcategory": "Sports", "color": "Grey", "price": 1299, "in_stock": True, "draw_fn": draw_sandal},
    {"name": "Formal Loafers", "category": "Footwear", "subcategory": "Formal", "color": "Brown", "price": 2499, "in_stock": True, "draw_fn": draw_shoe},
    {"name": "Basketball Shoes", "category": "Footwear", "subcategory": "Sports", "color": "Red", "price": 4999, "in_stock": True, "draw_fn": draw_sneaker},
    {"name": "Basketball Shoes", "category": "Footwear", "subcategory": "Sports", "color": "White", "price": 4999, "in_stock": True, "draw_fn": draw_shoe},
    {"name": "Wedge Sandals", "category": "Footwear", "subcategory": "Heels", "color": "Tan", "price": 1799, "in_stock": True, "draw_fn": draw_sandal},
    {"name": "Hiking Boots", "category": "Footwear", "subcategory": "Boots", "color": "Brown", "price": 5499, "in_stock": True, "draw_fn": draw_boot},
    {"name": "Slip-On Sneakers", "category": "Footwear", "subcategory": "Casual", "color": "Navy", "price": 1499, "in_stock": True, "draw_fn": draw_sneaker},
    {"name": "Slip-On Sneakers", "category": "Footwear", "subcategory": "Casual", "color": "Grey", "price": 1499, "in_stock": True, "draw_fn": draw_sneaker},
    {"name": "Combat Boots", "category": "Footwear", "subcategory": "Boots", "color": "Black", "price": 4499, "in_stock": True, "draw_fn": draw_boot},
    {"name": "Espadrilles", "category": "Footwear", "subcategory": "Casual", "color": "Beige", "price": 799, "in_stock": True, "draw_fn": draw_shoe},
    {"name": "Running Sneakers", "category": "Footwear", "subcategory": "Sports", "color": "Blue", "price": 2999, "in_stock": True, "draw_fn": draw_sneaker},
    {"name": "Leather Oxford Shoes", "category": "Footwear", "subcategory": "Formal", "color": "Tan", "price": 3499, "in_stock": True, "draw_fn": draw_shoe},
    {"name": "Platform Heels", "category": "Footwear", "subcategory": "Heels", "color": "Black", "price": 2999, "in_stock": True, "draw_fn": draw_sandal},
    {"name": "Trail Running Shoes", "category": "Footwear", "subcategory": "Sports", "color": "Teal", "price": 3999, "in_stock": True, "draw_fn": draw_sneaker},

    # ── ELECTRONICS ── (30 products)
    {"name": "Wireless Earbuds", "category": "Electronics", "subcategory": "Audio", "color": "White", "price": 2499, "in_stock": True, "draw_fn": draw_earbuds},
    {"name": "Wireless Earbuds", "category": "Electronics", "subcategory": "Audio", "color": "Black", "price": 2499, "in_stock": True, "draw_fn": draw_earbuds},
    {"name": "Smartwatch", "category": "Electronics", "subcategory": "Wearables", "color": "Black", "price": 4999, "in_stock": True, "draw_fn": draw_watch},
    {"name": "Smartwatch", "category": "Electronics", "subcategory": "Wearables", "color": "Silver", "price": 5499, "in_stock": True, "draw_fn": draw_watch},
    {"name": "Bluetooth Speaker", "category": "Electronics", "subcategory": "Audio", "color": "Black", "price": 1999, "in_stock": True, "draw_fn": draw_speaker},
    {"name": "USB-C Charging Hub", "category": "Electronics", "subcategory": "Accessories", "color": "Grey", "price": 1499, "in_stock": True, "draw_fn": draw_small_rect},
    {"name": "Mechanical Keyboard", "category": "Electronics", "subcategory": "Peripherals", "color": "Black", "price": 3999, "in_stock": True, "draw_fn": draw_keyboard},
    {"name": "Portable Power Bank", "category": "Electronics", "subcategory": "Accessories", "color": "Black", "price": 1299, "in_stock": True, "draw_fn": draw_small_rect},
    {"name": "Wireless Mouse", "category": "Electronics", "subcategory": "Peripherals", "color": "White", "price": 899, "in_stock": False, "draw_fn": draw_mouse},
    {"name": "Noise Cancelling Headphones", "category": "Electronics", "subcategory": "Audio", "color": "Black", "price": 7999, "in_stock": True, "draw_fn": draw_headphones},
    {"name": "Smart LED Bulb", "category": "Electronics", "subcategory": "Smart Home", "color": "White", "price": 499, "in_stock": True, "draw_fn": draw_bulb},
    {"name": "43-inch Smart TV", "category": "Electronics", "subcategory": "TV", "color": "Black", "price": 24999, "in_stock": True, "draw_fn": draw_tv},
    {"name": "Action Camera", "category": "Electronics", "subcategory": "Cameras", "color": "Black", "price": 15999, "in_stock": True, "draw_fn": draw_camera},
    {"name": "E-Reader", "category": "Electronics", "subcategory": "Tablets", "color": "Black", "price": 8999, "in_stock": True, "draw_fn": draw_reader},
    {"name": "Bluetooth Speaker", "category": "Electronics", "subcategory": "Audio", "color": "Red", "price": 1999, "in_stock": True, "draw_fn": draw_speaker},
    {"name": "Wireless Earbuds", "category": "Electronics", "subcategory": "Audio", "color": "Teal", "price": 3499, "in_stock": True, "draw_fn": draw_earbuds},
    {"name": "Gaming Mouse", "category": "Electronics", "subcategory": "Peripherals", "color": "Black", "price": 1499, "in_stock": True, "draw_fn": draw_mouse},
    {"name": "Webcam HD", "category": "Electronics", "subcategory": "Peripherals", "color": "Black", "price": 2999, "in_stock": True, "draw_fn": draw_small_rect},
    {"name": "Portable SSD", "category": "Electronics", "subcategory": "Accessories", "color": "Silver", "price": 3999, "in_stock": True, "draw_fn": draw_small_rect},
    {"name": "Portable Power Bank", "category": "Electronics", "subcategory": "Accessories", "color": "White", "price": 1299, "in_stock": True, "draw_fn": draw_small_rect},
    {"name": "Smart LED Bulb", "category": "Electronics", "subcategory": "Smart Home", "color": "Colorful", "price": 699, "in_stock": True, "draw_fn": draw_bulb, "color_override": (100, 180, 255)},
    {"name": "Tablet Stand", "category": "Electronics", "subcategory": "Accessories", "color": "Silver", "price": 999, "in_stock": True, "draw_fn": draw_small_rect},
    {"name": "Smartwatch", "category": "Electronics", "subcategory": "Wearables", "color": "Gold", "price": 7999, "in_stock": True, "draw_fn": draw_watch},
    {"name": "Mechanical Keyboard", "category": "Electronics", "subcategory": "Peripherals", "color": "White", "price": 4499, "in_stock": True, "draw_fn": draw_keyboard},
    {"name": "Noise Cancelling Headphones", "category": "Electronics", "subcategory": "Audio", "color": "Silver", "price": 8999, "in_stock": True, "draw_fn": draw_headphones},
    {"name": "Monitor Light Bar", "category": "Electronics", "subcategory": "Accessories", "color": "Black", "price": 1999, "in_stock": True, "draw_fn": draw_bulb},
    {"name": "Wireless Charger", "category": "Electronics", "subcategory": "Accessories", "color": "Black", "price": 1499, "in_stock": True, "draw_fn": draw_small_rect},
    {"name": "Wireless Charger", "category": "Electronics", "subcategory": "Accessories", "color": "White", "price": 1499, "in_stock": True, "draw_fn": draw_small_rect},
    {"name": "Smart Scale", "category": "Electronics", "subcategory": "Wearables", "color": "White", "price": 2499, "in_stock": True, "draw_fn": draw_small_rect},
    {"name": "Smart Scale", "category": "Electronics", "subcategory": "Wearables", "color": "Black", "price": 2499, "in_stock": True, "draw_fn": draw_small_rect},

    # ── HOME ── (30 products)
    {"name": "Ceramic Coffee Mug", "category": "Home", "subcategory": "Kitchen", "color": "White", "price": 349, "in_stock": True, "draw_fn": draw_mug},
    {"name": "Ceramic Coffee Mug", "category": "Home", "subcategory": "Kitchen", "color": "Black", "price": 349, "in_stock": True, "draw_fn": draw_mug},
    {"name": "Scented Candle", "category": "Home", "subcategory": "Decor", "color": "Beige", "price": 599, "in_stock": True, "draw_fn": draw_candle},
    {"name": "Cotton Throw Blanket", "category": "Home", "subcategory": "Bedding", "color": "Grey", "price": 999, "in_stock": True, "draw_fn": draw_blanket},
    {"name": "Cotton Throw Blanket", "category": "Home", "subcategory": "Bedding", "color": "Cream", "price": 999, "in_stock": True, "draw_fn": draw_blanket},
    {"name": "Wooden Serving Tray", "category": "Home", "subcategory": "Kitchen", "color": "Brown", "price": 799, "in_stock": True, "draw_fn": draw_tray},
    {"name": "Stainless Steel Water Bottle", "category": "Home", "subcategory": "Kitchen", "color": "Silver", "price": 699, "in_stock": True, "draw_fn": draw_bottle},
    {"name": "Stainless Steel Water Bottle", "category": "Home", "subcategory": "Kitchen", "color": "Black", "price": 699, "in_stock": True, "draw_fn": draw_bottle},
    {"name": "Indoor Plant Pot", "category": "Home", "subcategory": "Decor", "color": "Terracotta", "price": 449, "in_stock": True, "draw_fn": draw_plant_pot},
    {"name": "Desk Organiser", "category": "Home", "subcategory": "Office", "color": "Black", "price": 899, "in_stock": True, "draw_fn": draw_organiser},
    {"name": "Bamboo Bath Towel", "category": "Home", "subcategory": "Bathroom", "color": "White", "price": 599, "in_stock": True, "draw_fn": draw_towel},
    {"name": "Picture Frame Set", "category": "Home", "subcategory": "Decor", "color": "Gold", "price": 799, "in_stock": True, "draw_fn": draw_frame},
    {"name": "Air Purifier", "category": "Home", "subcategory": "Appliances", "color": "White", "price": 7999, "in_stock": True, "draw_fn": draw_purifier},
    {"name": "Robot Vacuum Cleaner", "category": "Home", "subcategory": "Appliances", "color": "Black", "price": 14999, "in_stock": True, "draw_fn": draw_vacuum},
    {"name": "Ceramic Coffee Mug", "category": "Home", "subcategory": "Kitchen", "color": "Teal", "price": 399, "in_stock": True, "draw_fn": draw_mug},
    {"name": "Glass Storage Jar", "category": "Home", "subcategory": "Kitchen", "color": "White", "price": 499, "in_stock": True, "draw_fn": draw_bottle},
    {"name": "Wool Blanket", "category": "Home", "subcategory": "Bedding", "color": "Burgundy", "price": 1999, "in_stock": True, "draw_fn": draw_blanket},
    {"name": "Wool Blanket", "category": "Home", "subcategory": "Bedding", "color": "Grey", "price": 1999, "in_stock": True, "draw_fn": draw_blanket},
    {"name": "Scented Candle", "category": "Home", "subcategory": "Decor", "color": "Lavender", "price": 699, "in_stock": True, "draw_fn": draw_candle},
    {"name": "Bamboo Cutting Board", "category": "Home", "subcategory": "Kitchen", "color": "Brown", "price": 599, "in_stock": True, "draw_fn": draw_tray},
    {"name": "Throw Pillow", "category": "Home", "subcategory": "Decor", "color": "Mustard", "price": 799, "in_stock": True, "draw_fn": draw_blanket},
    {"name": "Throw Pillow", "category": "Home", "subcategory": "Decor", "color": "Cream", "price": 799, "in_stock": True, "draw_fn": draw_blanket},
    {"name": "Bath Mat", "category": "Home", "subcategory": "Bathroom", "color": "Teal", "price": 449, "in_stock": True, "draw_fn": draw_towel},
    {"name": "Ceramic Vase", "category": "Home", "subcategory": "Decor", "color": "White", "price": 899, "in_stock": True, "draw_fn": draw_bottle},
    {"name": "Wall Clock", "category": "Home", "subcategory": "Decor", "color": "Black", "price": 1299, "in_stock": True, "draw_fn": draw_watch},
    {"name": "Glass Water Bottle", "category": "Home", "subcategory": "Kitchen", "color": "Clear", "price": 599, "in_stock": True, "draw_fn": draw_bottle, "color_override": (200, 210, 220)},
    {"name": "Scented Candle", "category": "Home", "subcategory": "Decor", "color": "Rose", "price": 699, "in_stock": True, "draw_fn": draw_candle, "color_override": (220, 150, 160)},
    {"name": "Indoor Plant Pot", "category": "Home", "subcategory": "Decor", "color": "White", "price": 499, "in_stock": True, "draw_fn": draw_plant_pot},
    {"name": "Desk Lamp", "category": "Home", "subcategory": "Office", "color": "Black", "price": 1499, "in_stock": True, "draw_fn": draw_bulb},
    {"name": "Storage Basket", "category": "Home", "subcategory": "Office", "color": "Beige", "price": 699, "in_stock": True, "draw_fn": draw_organiser},

    # ── BEAUTY ── (20 products)
    {"name": "Vitamin C Serum", "category": "Beauty", "subcategory": "Skincare", "color": "Orange", "price": 799, "in_stock": True, "draw_fn": draw_dropper},
    {"name": "Matte Lipstick", "category": "Beauty", "subcategory": "Makeup", "color": "Red", "price": 449, "in_stock": True, "draw_fn": draw_lipstick},
    {"name": "Matte Lipstick", "category": "Beauty", "subcategory": "Makeup", "color": "Nude", "price": 449, "in_stock": True, "draw_fn": draw_lipstick},
    {"name": "Argan Hair Oil", "category": "Beauty", "subcategory": "Haircare", "color": "Amber", "price": 599, "in_stock": True, "draw_fn": draw_hair_oil},
    {"name": "SPF 50 Sunscreen", "category": "Beauty", "subcategory": "Skincare", "color": "White", "price": 399, "in_stock": True, "draw_fn": draw_tube},
    {"name": "Eyeshadow Palette", "category": "Beauty", "subcategory": "Makeup", "color": "Multicolor", "price": 1299, "in_stock": True, "draw_fn": draw_palette},
    {"name": "Face Wash Gel", "category": "Beauty", "subcategory": "Skincare", "color": "Green", "price": 299, "in_stock": True, "draw_fn": draw_tube},
    {"name": "Perfume Eau de Toilette", "category": "Beauty", "subcategory": "Fragrance", "color": "Gold", "price": 1999, "in_stock": True, "draw_fn": draw_perfume},
    {"name": "Nourishing Face Cream", "category": "Beauty", "subcategory": "Skincare", "color": "White", "price": 599, "in_stock": True, "draw_fn": draw_tube},
    {"name": "Eye Cream", "category": "Beauty", "subcategory": "Skincare", "color": "Peach", "price": 699, "in_stock": True, "draw_fn": draw_dropper},
    {"name": "Matte Lipstick", "category": "Beauty", "subcategory": "Makeup", "color": "Pink", "price": 449, "in_stock": True, "draw_fn": draw_lipstick},
    {"name": "Shampoo", "category": "Beauty", "subcategory": "Haircare", "color": "White", "price": 399, "in_stock": True, "draw_fn": draw_bottle},
    {"name": "Body Lotion", "category": "Beauty", "subcategory": "Skincare", "color": "Lavender", "price": 499, "in_stock": True, "draw_fn": draw_tube},
    {"name": "Perfume Eau de Toilette", "category": "Beauty", "subcategory": "Fragrance", "color": "Blush", "price": 2499, "in_stock": True, "draw_fn": draw_perfume},
    {"name": "Setting Spray", "category": "Beauty", "subcategory": "Makeup", "color": "Black", "price": 399, "in_stock": True, "draw_fn": draw_bottle},
    {"name": "Lip Gloss", "category": "Beauty", "subcategory": "Makeup", "color": "Coral", "price": 349, "in_stock": True, "draw_fn": draw_lipstick},
    {"name": "Face Mask Sheet", "category": "Beauty", "subcategory": "Skincare", "color": "White", "price": 199, "in_stock": True, "draw_fn": draw_blanket},
    {"name": "Hair Serum", "category": "Beauty", "subcategory": "Haircare", "color": "Gold", "price": 799, "in_stock": True, "draw_fn": draw_dropper},
    {"name": "Mascara", "category": "Beauty", "subcategory": "Makeup", "color": "Black", "price": 599, "in_stock": True, "draw_fn": draw_lipstick},
    {"name": "Beauty Sponge Set", "category": "Beauty", "subcategory": "Makeup", "color": "Pink", "price": 299, "in_stock": True, "draw_fn": draw_earbuds},
]


def generate():
    print(f"[Generator] Creating {len(PRODUCTS)} synthetic products with programmatic images...")

    rows = []
    for idx, product in enumerate(tqdm(PRODUCTS, desc="Generating products")):
        product_id = idx + 1
        filename = f"product_{product_id:04d}.jpg"
        filepath = IMAGES_DIR / filename

        color_name = product["color"]
        color_rgb = product.get("color_override") or COLORS.get(color_name, (200, 200, 200))

        img, draw = _make_bg(category=product["category"])
        _draw_bg_texture(draw, product_id, product["category"])
        product["draw_fn"](draw, color_rgb)
        img = _shadow(img)
        img.save(str(filepath), "JPEG", quality=90)

        rows.append({
            "id": product_id,
            "name": product["name"],
            "category": product["category"],
            "subcategory": product["subcategory"],
            "color": product["color"],
            "price": product["price"],
            "in_stock": product["in_stock"],
            "stock_count": random.randint(0, 100) if product["in_stock"] else 0,
            "image_path": f"data/synthetic/images/{filename}",
            "description": f"{product['color']} {product['name']} — {product['subcategory']}",
        })

    with open(METADATA_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    cats = {}
    for r in rows:
        cats[r["category"]] = cats.get(r["category"], 0) + 1

    print(f"\n[Generator] ✓ Done. {len(rows)} products generated.")
    print(f"[Generator] CSV: {METADATA_FILE}")
    print(f"[Generator] Images: {IMAGES_DIR}/")
    print(f"\nCategory distribution:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat:<15} {count}")
    print(f"\nEdge cases included:")
    print("  ✓ Same product, multiple colors")
    print("  ✓ Near-duplicate products")
    print("  ✓ Out-of-stock variants")
    print("  ✓ Wide price range per category")
    print("  ✓ Category boundary items")
    print("  ✓ Programmatic images (no API dependency)")


if __name__ == "__main__":
    generate()
