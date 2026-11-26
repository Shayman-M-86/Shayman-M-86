"""Render repository-hosted gallery cards from Notion covers and public text."""
from io import BytesIO
from pathlib import Path
import hashlib
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, COVER, PAD = 640, 360, 30


def font(size, bold=False):
    candidates = (
        ["C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
        if bold else
        ["C:/Windows/Fonts/segoeui.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise RuntimeError("A Segoe UI or DejaVu Sans font is required.")


def wrap(text, face, width):
    """Wrap by measured pixels, including unusually long words."""
    lines, line = [], ""
    for word in " ".join(text.split()).split(" "):
        if not word:
            continue
        pieces = [word]
        if face.getlength(word) > width:
            pieces, part = [], ""
            for char in word:
                if part and face.getlength(part + char) > width:
                    pieces.append(part)
                    part = ""
                part += char
            if part:
                pieces.append(part)
        for piece in pieces:
            candidate = (line + " " + piece).strip()
            if line and face.getlength(candidate) > width:
                lines.append(line)
                line = piece
            else:
                line = candidate
    if line:
        lines.append(line)
    return lines


def load_cover(row):
    cover = row.get("cover") or {}
    kind = cover.get("type")
    url = cover.get(kind, {}).get("url") if kind in ("file", "external") else None
    if not url:
        image = Image.new("RGB", (WIDTH, COVER), "#162b3b")
        draw = ImageDraw.Draw(image)
        for x in range(-COVER, WIDTH, 48):
            draw.line((x, 0, x + COVER, COVER), fill="#294b59", width=2)
        return image
    if urlsplit(url).scheme != "https":
        raise ValueError("Cover images must use HTTPS.")
    try:
        with urlopen(Request(url, headers={"User-Agent": "FlowForm-profile-gallery"}), timeout=30) as response:
            content = response.read(20_000_001)
        if len(content) > 20_000_000:
            raise ValueError("Cover image exceeds the download limit.")
        with Image.open(BytesIO(content)) as image:
            return ImageOps.exif_transpose(image).convert("RGB")
    except Exception:
        # Signed URLs can contain credentials; never print the URL or its error.
        raise RuntimeError("Could not read a Notion cover; gallery was left unchanged.") from None


def render_cards(ideas, destination):
    """Return content-addressed images, with equal heights and no clipped text."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    title_font, body_font = font(34, True), font(28)
    layouts = [
        (idea, wrap(idea["title"], title_font, WIDTH - PAD * 2),
         wrap(idea["summary"], body_font, WIDTH - PAD * 2))
        for idea in ideas
    ]
    height = max(
        (COVER + PAD + len(title) * 43 + 22 + len(body) * 38 + 42
         for _, title, body in layouts), default=0
    )
    paths = []
    for idea, title, body in layouts:
        card = Image.new("RGB", (WIDTH, height), "#523820")
        card.paste(ImageOps.fit(load_cover(idea["row"]), (WIDTH, COVER), centering=(.5, .5)), (0, 0))
        draw = ImageDraw.Draw(card)
        y = COVER + PAD
        for line in title:
            draw.text((PAD, y), line, font=title_font, fill="#fff8ef")
            y += 43
        y += 22
        for line in body:
            draw.text((PAD, y), line, font=body_font, fill="#f4e9df")
            y += 38
        rounded = Image.new("L", card.size, 0)
        ImageDraw.Draw(rounded).rounded_rectangle((0, 0, WIDTH-1, height-1), radius=22, fill=255)
        result = card.convert("RGBA")
        result.putalpha(rounded)
        ImageDraw.Draw(result).rounded_rectangle((0, 0, WIDTH-1, height-1), radius=22, outline="#69503b", width=2)
        buffer = BytesIO()
        result.save(buffer, format="WEBP", quality=95, method=6)
        content = buffer.getvalue()
        path = destination / ("idea-" + hashlib.sha256(content).hexdigest()[:16] + ".webp")
        path.write_bytes(content)
        paths.append(path)
    return paths
