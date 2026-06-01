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

# Final output sizes
BANNER_W = 1080
BANNER_H = 600

POSTER_W = 1080
POSTER_H = 1080

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
# PROMPT HELPERS
# ======================================================

def normalize_style(style: str) -> str:
    value = (style or "auto").lower()

    if "grab" in value:
        return "GrabFood style, modern food delivery campaign, optimized for food ordering conversion"
    if "foodpanda" in value:
        return "Foodpanda style, bright modern food delivery campaign, appetizing and platform-friendly"
    if "luxury" in value:
        return "Luxury restaurant campaign, premium commercial lighting, elegant and high-end"
    if "japanese" in value:
        return "Japanese clean restaurant style, minimal, elegant, natural wood textures and refined lighting"
    if "premium" in value:
        return "Premium food photography, professional commercial food advertising"

    return "AI auto detect: choose the most suitable advertising style based on the uploaded food"


def clean_text(value: str) -> str:
    return (value or "").strip()


def optional_text_rules(title: str, subtitle: str, badge: str, price: str) -> str:
    rules = []

    if clean_text(title):
        rules.append(f'Main Title: "{clean_text(title)}"')
    if clean_text(subtitle):
        rules.append(f'Subtitle: "{clean_text(subtitle)}"')
    if clean_text(badge):
        rules.append(f'Badge: "{clean_text(badge)}"')
    if clean_text(price):
        rules.append(f'Price: "{clean_text(price)}"')

    if not rules:
        return "No user text provided. Do not invent any words."

    return "\n".join(rules)


def typography_rules() -> str:
    return """
TYPOGRAPHY REQUIREMENTS:
- Generate all typography directly inside the artwork using GPT Image 2.
- Do not leave typography to HTML, CSS, PIL, or external overlay.
- Do not use generic default fonts or plain system fonts.
- Create custom premium food advertising typography.
- Design the main title font, subtitle font, badge style, price style, spacing, hierarchy, shadow, highlight and depth.
- Chinese text must look like modern premium Chinese campaign lettering, not default system Chinese font.
- English text must look like professional editorial / campaign display typography.
- Typography should match the food category and dining scene.
- Keep all user-provided text readable.
- Use only exact user-provided text.
- Do not invent extra words.
- Do not create fake platform text, fake discount text, fake labels, watermark, random words or brand marks.
"""


# ======================================================
# GPT IMAGE PROMPTS
# ======================================================

def build_banner_prompt(title: str, subtitle: str, badge: str, price: str, style: str) -> str:
    return f"""
Analyze the uploaded food image carefully.

Your task is to create a premium food delivery advertisement banner.

FINAL OUTPUT:
- 1080px × 600px horizontal banner.
- Professional GrabFood / Foodpanda style advertising banner.
- Commercial food marketing quality.
- No watermark.
- No border.
- No fake platform UI.
- No random text.
- No stock photo appearance.

FOOD ANALYSIS:
First identify:
- food type
- cuisine category
- serving style
- ingredients
- dining experience
- cultural origin
- whether it is hot food, cold food, drink, dessert, rice dish, noodles, roasted meat, fried food, Japanese food, Korean food, Indonesian food, local Malaysian food, western food, or premium restaurant dish.

SCENE GENERATION:
Generate a realistic advertising background scene that naturally matches the uploaded food.

The scene must feel:
- authentic
- premium
- restaurant quality
- professionally photographed
- naturally connected to the food category

Examples:
- Pork chop rice: warm restaurant table, freshly grilled atmosphere, hot meal feeling.
- Smoked duck rice: warm roasted meat restaurant atmosphere, rich roasted tones.
- Babi gepuk: Indonesian rustic dining style, sambal atmosphere, warm traditional table.
- Japanese food: clean Japanese restaurant setting, wood textures, refined minimal lighting.
- Korean food: modern Korean dining or Korean street food atmosphere.
- Noodles: warm kitchen, hawker, kopitiam, or restaurant atmosphere depending on the dish.
- Dessert: clean cafe atmosphere, soft light, sweet premium mood.
- Drink: refreshing beverage scene, clean commercial lighting.

IMPORTANT COLOR RULE:
- Do not use corporate brand colors.
- Do not force teal, cyan, blue, red, or any fixed color palette.
- Choose colors naturally based on the uploaded food itself.
- The color palette must support the food and make it appetizing.

FOOD PRESERVATION:
The uploaded food must remain recognizable.
Do not replace the food.
Do not change the dish type.
Do not change the meat type.
Do not replace ingredients.
Do not remove the main product.
Do not transform it into another dish.

Improve:
- texture
- lighting
- sharpness
- food styling
- presentation
while preserving the actual food identity.

HOT FOOD EFFECT:
If the uploaded food is hot food, make it look freshly cooked, hot, appetizing and just served.
Add subtle natural steam rising from the food.
Steam must be:
- realistic
- elegant
- light
- natural
- not too strong
- not blocking the food
- not blocking text
- not entering the logo clean zone

If the uploaded item is cold food, dessert, or drink, do not add hot steam unless naturally suitable.

CRITICAL CANVAS MAP:
- Full banner canvas: 1080 wide × 600 high.
- Text safe area: X 60 to 520, Y 150 to 560.
- Food safe area: X 610 to 1020, Y 170 to 560.
- Logo clean zone: X 860 to 1060, Y 20 to 140.
- Top danger area: Y 0 to 145. No important text or important food here.
- Bottom danger area: Y 570 to 600. No important text or important food here.

FIXED BANNER LAYOUT:
RIGHT SIDE FOOD:
- Food product must be mainly inside X 610 to 1020 and Y 170 to 560.
- Food product center should be around X 760, Y 390.
- Food should occupy around 30% to 38% of banner width.
- Keep full product visible as much as possible.
- Do not crop plate, bowl, box, cup, or important food parts.
- Do not cover title, subtitle, badge, price, or logo area.
- Food must not enter X 860 to 1060, Y 20 to 140.

TOP RIGHT LOGO SAFE AREA:
- Keep X 860 to 1060, Y 20 to 140 completely clean.
- This zone must contain only simple background / negative space.
- No food.
- No text.
- No decorations.
- No smoke.
- No steam.
- No garnish.
- No bright objects.
- No fake logo.

LEFT SIDE TEXT SAFE AREA:
- All typography must stay inside X 60 to 520 and Y 150 to 560.
- Do not place any title, subtitle, badge, price, CTA, label, decoration text, or small text outside this safe area.
- Leave enough clean background behind the typography for readability.

STRICT TEXT POSITIONS:
- Main title must be inside X 60 to 500 and Y 180 to 320.
- If title is long, wrap it into maximum 2 lines and reduce font size automatically.
- Subtitle must be inside X 60 to 500 and Y 320 to 390, only if subtitle is provided.
- Badge must be inside X 60 to 270 and Y 430 to 520, only if badge is provided.
- Price must be inside X 300 to 520 and Y 430 to 520, only if price is provided.
- Badge and price must not overlap each other.
- Badge and price must not overlap the food.
- Badge and price must not go below Y 560.

TEXT FITTING RULE:
- Automatically resize typography to fit the safe area.
- Readability and staying inside safe area are more important than large text.
- Never allow title overflow.
- Never allow subtitle overflow.
- Never allow badge overflow.
- Never allow price overflow.
- Never place any text outside X 60 to 520 and Y 150 to 560.
- If a title is too long, make it smaller or use up to 2 lines.
- If badge or price is too long, make it smaller and keep it inside the assigned box.

TYPOGRAPHY:
{typography_rules()}

TYPOGRAPHY STYLE BY FOOD:
- Japanese food: clean elegant typography.
- Street food: bold energetic typography.
- Premium dining: luxury editorial typography.
- Local food: warm appetizing campaign typography.
- Western food: bold modern restaurant typography.
- Dessert: soft elegant cafe typography.
- Drink: fresh clean beverage typography.

OPTIONAL RULES:
- If subtitle is empty, do not create subtitle, slogan, tagline, or extra small text.
- If badge is empty, do not create badge, sticker, ribbon, label, or placeholder.
- If price is empty, do not create price, currency, discount, number, price box, or placeholder.
- Only use user-provided text.
- Do not invent additional words.

ABSOLUTE NEGATIVE RULES:
- No text above Y 150.
- No text below Y 560.
- No text outside X 60 to 520.
- No badge outside X 60 to 270, Y 430 to 520.
- No price outside X 300 to 520, Y 430 to 520.
- No food, text, steam, smoke or decoration in logo clean zone X 860 to 1060, Y 20 to 140.
- No safe area guide lines.
- No visible boxes showing safe area.
- No rulers.
- No dashed lines.
- No template guides.

STYLE OPTION:
{normalize_style(style)}

USER TEXT:
{optional_text_rules(title, subtitle, badge, price)}
"""


def build_poster_prompt(title: str, subtitle: str, badge: str, price: str, style: str) -> str:
    return f"""
Analyze the uploaded food image carefully.

Your task is to create a premium square food advertisement poster.

FINAL OUTPUT:
- 1:1 square poster.
- Professional food advertising poster.
- Suitable for GrabFood, Foodpanda, Instagram, Facebook, menu promotion and food campaign usage.
- No watermark.
- No border.
- No fake platform UI.
- No random text.

IMPORTANT RATIO RULE:
- Poster must be 1:1 square.
- Do not create vertical 4:5 poster.
- Do not create horizontal banner.

FOOD ANALYSIS:
Identify:
- food type
- cuisine category
- ingredients
- serving style
- cultural origin
- dining atmosphere
- whether it is hot food, cold food, dessert, drink, rice dish, noodles, fried food, roasted meat, Japanese food, Korean food, Indonesian food, Malaysian local food, western food, or premium dining dish.

SCENE GENERATION:
Generate a background scene that naturally matches the uploaded food.

Examples:
- Pork chop rice: warm restaurant table, freshly grilled atmosphere, hot meal feeling.
- Smoked duck rice: warm roasted meat restaurant atmosphere, rich roasted tones.
- Babi gepuk: Indonesian rustic dining style, sambal atmosphere, warm traditional table.
- Japanese food: clean Japanese restaurant setting, wood textures, refined lighting.
- Korean food: Korean dining or street food atmosphere.
- Noodles: warm kitchen, hawker, kopitiam, or restaurant atmosphere depending on the dish.
- Dessert: clean cafe atmosphere, soft light, sweet premium mood.
- Drink: refreshing beverage scene, clean commercial lighting.

IMPORTANT COLOR RULE:
- Do not use corporate brand colors.
- Do not force teal, cyan, blue, red, or any fixed color palette.
- Choose the color palette based on the uploaded food and the suitable dining scene.
- The design should make the food look appetizing and high-converting.

FOOD PRESERVATION:
The uploaded food must remain recognizable.
Do not change the dish into another dish.
Do not replace meat or ingredients.
Do not remove the main product.
Improve the food appearance while preserving the real food identity.

HOT FOOD EFFECT:
If the uploaded food is hot food, make it feel freshly served and hot.
Add subtle natural steam if suitable.
Steam should be:
- soft
- realistic
- appetizing
- light
- not too strong
- not blocking the food
- not blocking text

If the uploaded item is cold food, dessert, or drink, do not add hot steam unless naturally suitable.

POSTER DESIGN:
Let AI freely create the best square advertising poster design.
Use professional art direction.
Create a high-converting food campaign visual.
The food should be the hero.
The layout should feel premium, modern, authentic and appetizing.
Design should look like a professional food brand campaign, not a template.

POSTER TEXT SAFETY:
- Keep all user-provided text fully inside the 1:1 canvas.
- Do not crop any title, subtitle, badge or price.
- Automatically resize text if needed.
- Long title can wrap into maximum 2 lines.
- Readability is more important than huge text.

TYPOGRAPHY:
{typography_rules()}

TYPOGRAPHY STYLE BY FOOD:
- Japanese food: clean elegant typography.
- Street food: bold energetic typography.
- Premium dining: luxury editorial typography.
- Local food: warm appetizing campaign typography.
- Western food: bold modern restaurant typography.
- Dessert: soft elegant cafe typography.
- Drink: fresh clean beverage typography.

OPTIONAL RULES:
- If subtitle is empty, do not create subtitle, slogan, tagline, or extra small text.
- If badge is empty, do not create badge, sticker, ribbon, label, or placeholder.
- If price is empty, do not create price, currency, discount, number, price box, or placeholder.
- Only use user-provided text.
- Do not invent additional words.

STYLE OPTION:
{normalize_style(style)}

USER TEXT:
{optional_text_rules(title, subtitle, badge, price)}
"""


def build_product_prompt(style: str) -> str:
    return f"""
Analyze the uploaded food image carefully.

Your task is to create a premium clean food product image.

FINAL OUTPUT:
- 1:1 square product image.
- Clean product photography.
- Suitable for menu, GrabFood, Foodpanda, ecommerce, POS system, and product listing.
- No text.
- No logo.
- No price.
- No badge.
- No watermark.
- No border.

IMPORTANT RATIO RULE:
- Product image must be 1:1 square.

BACKGROUND:
Use a clean white, off-white, or very light neutral studio background.
Do not create restaurant scene.
Do not create colored advertising background.
Do not use corporate brand colors.
Do not force teal, cyan, red, blue, or any fixed color palette.

FOOD PRESERVATION:
Preserve the uploaded food identity.
Do not change the dish type.
Do not replace ingredients.
Do not add unrelated food.
Do not remove the main product.
Do not crop important parts.

PRODUCT PRESENTATION:
- Remove messy original background.
- Center the product.
- Keep the full plate, bowl, box, cup, or food visible.
- Product should occupy about 65% to 78% of the image.
- Add soft natural contact shadow.
- Make food look sharp, appetizing, realistic and premium.
- Use clean commercial menu photography.

HOT FOOD EFFECT:
If the food is hot food, add very subtle natural steam.
Steam must be light, elegant and realistic.
Do not overdo smoke.
If the uploaded item is cold food, dessert, or drink, do not add hot steam unless naturally suitable.

STRICT NEGATIVE:
- No text.
- No random words.
- No logo.
- No price.
- No badge.
- No hands.
- No people.
- No table scene.
- No restaurant scene.
- No props unless already part of the food.
- No unrelated ingredients.

STYLE OPTION:
{normalize_style(style)}
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
        openai_size = "1024x1024"
        suffix = "poster_1080x1080"
        target_w, target_h = POSTER_W, POSTER_H

    image_bytes = call_openai_image_edit(image_path, prompt, openai_size)

    filename = f"{int(time.time() * 1000)}_{suffix}.png"
    output_path = OUTPUT_FOLDER / filename

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    if visual_type == "banner":
        resize_cover(str(output_path), target_w, target_h)
    else:
        resize_exact(str(output_path), target_w, target_h)

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
        "poster_size": f"{POSTER_W}x{POSTER_H}",
        "product_size": f"{PRODUCT_W}x{PRODUCT_H}",
        "banner_size": f"{BANNER_W}x{BANNER_H}",
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")
