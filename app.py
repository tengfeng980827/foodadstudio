import os
import time
import base64
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from openai import OpenAI
from PIL import Image
from werkzeug.utils import secure_filename


# ======================================================
# ENV / APP SETUP
# ======================================================

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
OUTPUT_FOLDER = BASE_DIR / "outputs"
LOGO_FOLDER = BASE_DIR / "logos"

UPLOAD_FOLDER.mkdir(exist_ok=True)
OUTPUT_FOLDER.mkdir(exist_ok=True)
LOGO_FOLDER.mkdir(exist_ok=True)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

BANNER_W = 1080
BANNER_H = 600
POSTER_W = 1080
POSTER_H = 1350
PRODUCT_W = 1080
PRODUCT_H = 1080

_client: Optional[OpenAI] = None


# ======================================================
# OPENAI CLIENT
# ======================================================

def get_openai_client() -> OpenAI:
    global _client

    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured in Railway Variables")
        _client = OpenAI(api_key=api_key)

    return _client


# ======================================================
# HELPERS
# ======================================================

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file, folder: Path) -> str:
    if not file or not file.filename:
        return ""

    if not allowed_file(file.filename):
        raise ValueError("Only PNG, JPG, JPEG or WEBP images are allowed.")

    ext = file.filename.rsplit(".", 1)[1].lower()
    safe_name = secure_filename(file.filename.rsplit(".", 1)[0])[:50]
    filename = f"{int(time.time() * 1000)}_{safe_name}.{ext}"
    raw_path = folder / filename
    file.save(raw_path)

    # Convert image to PNG for OpenAI compatibility and cleaner processing
    try:
        img = Image.open(raw_path).convert("RGBA")
        fixed_filename = f"{int(time.time() * 1000)}_{safe_name}_fixed.png"
        fixed_path = folder / fixed_filename
        img.save(fixed_path, "PNG")

        try:
            raw_path.unlink()
        except Exception:
            pass

        return str(fixed_path)
    except Exception:
        return str(raw_path)


def resize_cover(image_path: str, target_w: int, target_h: int) -> None:
    img = Image.open(image_path).convert("RGBA")
    iw, ih = img.size

    target_ratio = target_w / target_h
    image_ratio = iw / ih

    if image_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * image_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / image_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))
    img.save(image_path)


def resize_exact(image_path: str, target_w: int, target_h: int) -> None:
    img = Image.open(image_path).convert("RGBA")
    img = img.resize((target_w, target_h), Image.LANCZOS)
    img.save(image_path)


def overlay_logo(image_path: str, logo_path: str, visual_type: str) -> None:
    if not logo_path or not os.path.exists(logo_path):
        return

    try:
        base = Image.open(image_path).convert("RGBA")
        logo = Image.open(logo_path).convert("RGBA")

        bw, bh = base.size

        if visual_type == "banner":
            max_w = 180
            max_h = 90
            margin_right = 36
            margin_top = 28
        else:
            max_w = int(bw * 0.22)
            max_h = int(bh * 0.10)
            margin_right = int(bw * 0.05)
            margin_top = int(bh * 0.04)

        lw, lh = logo.size
        scale = min(max_w / lw, max_h / lh)
        nw = max(1, int(lw * scale))
        nh = max(1, int(lh * scale))

        logo = logo.resize((nw, nh), Image.LANCZOS)

        x = bw - nw - margin_right
        y = margin_top

        base.alpha_composite(logo, (x, y))
        base.save(image_path)
    except Exception:
        # Logo overlay should not break the whole generation
        return


def output_url(filename: str) -> str:
    return f"/outputs/{filename}"


def list_recent_outputs(limit: int = 12):
    files = []
    for path in OUTPUT_FOLDER.glob("*.png"):
        files.append(path)

    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    return [
        {
            "filename": p.name,
            "image_url": output_url(p.name),
            "download_url": f"/download/{p.name}",
            "created_at": int(p.stat().st_mtime),
        }
        for p in files[:limit]
    ]


# ======================================================
# PROMPTS
# ======================================================

def normalize_style(style: str) -> str:
    value = (style or "auto").lower()

    if "grab" in value:
        return "GrabFood style, modern food delivery platform campaign"
    if "foodpanda" in value:
        return "Foodpanda style, bright modern food delivery campaign"
    if "luxury" in value:
        return "Luxury restaurant campaign, premium dark commercial lighting"
    if "japanese" in value:
        return "Japanese clean restaurant style, minimal, elegant and premium"
    if "premium" in value:
        return "Premium food photography, professional commercial food advertising"

    return "AI automatically detects the best premium food advertising style"


def optional_text_rules(title: str, subtitle: str, badge: str, price: str) -> str:
    rules = []

    if title.strip():
        rules.append(f'Main title: "{title.strip()}"')

    if subtitle.strip():
        rules.append(f'Subtitle: "{subtitle.strip()}"')

    if badge.strip():
        rules.append(f'Badge text: "{badge.strip()}"')

    if price.strip():
        rules.append(f'Price text: "{price.strip()}"')

    if not rules:
        return "No text elements except natural design elements. Do not invent words."

    return "\n".join(rules)


def typography_rules() -> str:
    return """
TYPOGRAPHY:
- Generate text as part of the artwork.
- Use premium custom food advertising typography.
- Chinese text must look like modern premium Chinese campaign lettering, not default system font.
- English text must look like professional editorial / campaign typography.
- Keep all user-provided text readable.
- Use only the exact user-provided text.
- Do not invent extra words.
- Do not create random labels, fake discounts, fake platform UI, or watermark.
"""


def build_banner_prompt(title: str, subtitle: str, badge: str, price: str, style: str) -> str:
    return f"""
Create a premium horizontal food delivery banner by editing the uploaded food photo.

FINAL OUTPUT:
- 1080px wide x 600px tall.
- Premium GrabFood / Foodpanda compatible food delivery banner.
- Full canvas background, no blurred side padding, no border, no watermark.

BRAND THEME:
- Main visual mood should match a corporate teal food-tech SaaS brand.
- Primary color inspiration: #006064, #00838F, #00ACC1.
- Red #D22928 may be used only for price, badge, or promo emphasis.

STYLE:
{normalize_style(style)}

LAYOUT:
- Top-right logo clean zone: X 860 to 1060, Y 20 to 140.
- Do not place food, text, badge, price, steam, garnish, or bright object inside the logo zone.
- Main food product should be on the right-center, around X 760 Y 390.
- Food should occupy around 30% to 38% of banner width.
- Keep the food appetizing, clear, realistic and not too zoomed out.
- Left side should be cleaner for text readability.
- All important text should stay inside Y 150 to Y 570.

TEXT POSITION:
- Main title on the left side.
- Subtitle below main title only if provided.
- Badge near bottom-left only if provided.
- Price near lower middle-left / near food only if provided.

OPTIONAL ELEMENT RULES:
- If subtitle is empty, do not generate subtitle or tagline.
- If badge is empty, do not generate badge, sticker, ribbon, label, or placeholder.
- If price is empty, do not generate price, currency, discount, price box, or placeholder.
- Use only text listed under USER TEXT.

{typography_rules()}

USER TEXT:
{optional_text_rules(title, subtitle, badge, price)}
"""


def build_poster_prompt(title: str, subtitle: str, badge: str, price: str, style: str) -> str:
    return f"""
Create a premium food delivery poster by editing the uploaded food photo.

FINAL OUTPUT:
- 4:5 vertical poster suitable for food delivery ads and social media.
- Premium commercial food advertising layout.
- No border, no watermark.

BRAND THEME:
- Corporate teal visual direction using #006064, #00838F, #00ACC1.
- Red #D22928 only for badge, price, or strong promo emphasis.

STYLE:
{normalize_style(style)}

LAYOUT:
- Food should be the hero element, large, appetizing, realistic and premium.
- Keep the whole food product visible where possible.
- Leave clean top-right space for logo overlay.
- Main title on the left or upper-left.
- Subtitle below title only if provided.
- Badge only if provided.
- Price only if provided.

OPTIONAL ELEMENT RULES:
- If subtitle is empty, do not generate subtitle or extra text.
- If badge is empty, do not generate badge or sticker.
- If price is empty, do not generate price, currency, sale amount, discount, or price placeholder.
- Use only text listed under USER TEXT.

{typography_rules()}

USER TEXT:
{optional_text_rules(title, subtitle, badge, price)}
"""


def build_product_prompt(style: str) -> str:
    return f"""
Create a clean premium product image by editing the uploaded food photo.

FINAL OUTPUT:
- 1:1 square product image.
- Clean white or very light teal-tinted background.
- No text, no logo, no price, no badge, no border, no watermark.

STYLE:
{normalize_style(style)}

PRODUCT RULES:
- Preserve the real food identity from the uploaded image.
- Remove messy original background.
- Keep food fully visible and centered.
- Product should occupy about 65% to 78% of the image.
- Add soft natural contact shadow.
- Bright clean commercial menu photography.
- Do not add extra food that was not uploaded.
- Do not crop the plate, bowl, box, cup or important food parts.
"""


# ======================================================
# IMAGE GENERATION
# ======================================================

def call_openai_image_edit(image_path: str, prompt: str, size: str) -> bytes:
    with open(image_path, "rb") as img:
        result = get_openai_client().images.edit(
            model=IMAGE_MODEL,
            image=[img],
            prompt=prompt,
            size=size,
        )

    return base64.b64decode(result.data[0].b64_json)


def generate_visual(
    image_path: str,
    logo_path: str,
    visual_type: str,
    title: str,
    subtitle: str,
    badge: str,
    price: str,
    style: str,
) -> str:
    visual_type = (visual_type or "poster").lower()

    if visual_type == "banner":
        prompt = build_banner_prompt(title, subtitle, badge, price, style)
        openai_size = "1536x1024"
        suffix = "banner_1080x600"
        target_w, target_h = BANNER_W, BANNER_H
    elif visual_type == "product":
        prompt = build_product_prompt(style)
        openai_size = "1024x1024"
        suffix = "product_1080x1080"
        target_w, target_h = PRODUCT_W, PRODUCT_H
    else:
        prompt = build_poster_prompt(title, subtitle, badge, price, style)
        openai_size = "1024x1536"
        suffix = "poster_1080x1350"
        target_w, target_h = POSTER_W, POSTER_H

    image_bytes = call_openai_image_edit(image_path, prompt, openai_size)

    filename = f"{int(time.time() * 1000)}_{suffix}.png"
    output_path = OUTPUT_FOLDER / filename

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    # Normalize final size
    if visual_type == "banner":
        resize_cover(str(output_path), target_w, target_h)
    else:
        resize_exact(str(output_path), target_w, target_h)

    # Overlay logo only for poster/banner, not product image
    if visual_type in {"poster", "banner"}:
        overlay_logo(str(output_path), logo_path, visual_type)

    return filename


# ======================================================
# ROUTES
# ======================================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    try:
        visual_type = request.form.get("type", "poster")
        title = request.form.get("title", "").strip()
        subtitle = request.form.get("subtitle", "").strip()
        badge = request.form.get("badge", "").strip()
        price = request.form.get("price", "").strip()
        style = request.form.get("style", "AI Auto Detect").strip()

        food_image = request.files.get("food_image")
        logo_file = request.files.get("logo")

        if not food_image or not food_image.filename:
            return jsonify({"success": False, "error": "Please upload food image."}), 400

        image_path = save_upload(food_image, UPLOAD_FOLDER)

        logo_path = ""
        if logo_file and logo_file.filename:
            logo_path = save_upload(logo_file, LOGO_FOLDER)

        filename = generate_visual(
            image_path=image_path,
            logo_path=logo_path,
            visual_type=visual_type,
            title=title,
            subtitle=subtitle,
            badge=badge,
            price=price,
            style=style,
        )

        return jsonify({
            "success": True,
            "filename": filename,
            "image_url": output_url(filename),
            "download_url": f"/download/{filename}",
            "recent": list_recent_outputs(6),
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/recent", methods=["GET"])
def api_recent():
    return jsonify({
        "success": True,
        "items": list_recent_outputs(12),
    })


@app.route("/outputs/<path:filename>")
def outputs(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)


@app.route("/download/<path:filename>")
def download(filename):
    path = OUTPUT_FOLDER / filename

    if not path.exists():
        return jsonify({"success": False, "error": "File not found."}), 404

    return send_file(path, as_attachment=True, download_name=filename)


# ======================================================
# SUPABASE AUTH BASIC ENDPOINTS
# ======================================================

@app.route("/auth/register", methods=["POST"])
def register():
    try:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            return jsonify({"success": False, "error": "Supabase variables not configured."}), 500

        data = request.get_json(force=True)
        email = data.get("email", "")
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"success": False, "error": "Email and password are required."}), 400

        r = requests.post(
            f"{SUPABASE_URL}/auth/v1/signup",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
            json={"email": email, "password": password},
            timeout=30,
        )

        return jsonify(r.json()), r.status_code

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/auth/login", methods=["POST"])
def login():
    try:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            return jsonify({"success": False, "error": "Supabase variables not configured."}), 500

        data = request.get_json(force=True)
        email = data.get("email", "")
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"success": False, "error": "Email and password are required."}), 400

        r = requests.post(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={
                "apikey": SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
            json={"email": email, "password": password},
            timeout=30,
        )

        return jsonify(r.json()), r.status_code

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ======================================================
# HEALTH CHECK
# ======================================================

@app.route("/health")
def health():
    return jsonify({
        "success": True,
        "status": "ok",
        "image_model": IMAGE_MODEL,
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_ANON_KEY),
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")
