from flask import Flask, request, send_file, render_template, jsonify
from openai import OpenAI
import os

# ==========================
# OPENAI CLIENT (Railway Safe)
# ==========================

_client = None

def get_openai_client():
    global _client

    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not configured in Railway Variables"
            )

        _client = OpenAI(api_key=api_key)

    return _client

from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from PIL import Image
import os
import base64
import time

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
LOGO_FOLDER = "logos"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(LOGO_FOLDER, exist_ok=True)

IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")

BANNER_W = 1080
BANNER_H = 600

PRODUCT_W = 1080
PRODUCT_H = 1080

SCENES = {
    "auto": "AI automatically chooses the most suitable premium food advertising scene",
    "plain": "Clean premium plain background",
    "kitchen": "Restaurant kitchen background",
    "japanese": "Japanese restaurant atmosphere",
    "hawker": "Malaysian hawker style",
    "luxury": "Dark luxury commercial food lighting"
}


BASE_CSS = """
<style>
:root{
    --bg:#070812;
    --panel:#0f1220;
    --panel2:#15192b;
    --card:#ffffff;
    --text:#0f172a;
    --muted:#64748b;
    --line:#e5e7eb;
    --dark:#070812;
    --orange:#ff7a1a;
    --orange2:#ffb86b;
    --yellow:#ffd166;
    --green:#17b26a;
    --blue:#3b82f6;
    --purple:#8b5cf6;
    --soft:#f8fafc;
    --radius:26px;
}
*{box-sizing:border-box;}
html{scroll-behavior:smooth;}
body{
    margin:0;
    font-family:Inter,Arial,"Microsoft YaHei",sans-serif;
    background:
        radial-gradient(circle at 12% 0%,rgba(255,122,26,.22),transparent 28%),
        radial-gradient(circle at 88% 8%,rgba(139,92,246,.20),transparent 26%),
        linear-gradient(180deg,#f8fafc 0%,#eef2f7 45%,#f8fafc 100%);
    color:var(--text);
}
a{text-decoration:none;color:inherit;}
.nav{
    height:76px;
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:0 46px;
    background:rgba(7,8,18,.88);
    backdrop-filter:blur(20px);
    border-bottom:1px solid rgba(255,255,255,.08);
    position:sticky;
    top:0;
    z-index:50;
}
.brand{
    display:flex;
    align-items:center;
    gap:13px;
    color:white;
    font-weight:950;
    letter-spacing:-.3px;
    font-size:19px;
}
.logo-mark{
    width:42px;
    height:42px;
    border-radius:15px;
    display:flex;
    align-items:center;
    justify-content:center;
    color:white;
    font-weight:950;
    background:linear-gradient(135deg,var(--orange),#fb4141);
    box-shadow:0 14px 30px rgba(255,122,26,.35);
}
.nav-links{
    display:flex;
    gap:8px;
    align-items:center;
}
.nav-links a{
    color:rgba(255,255,255,.75);
    padding:10px 15px;
    border-radius:999px;
    font-weight:800;
    font-size:14px;
}
.nav-links a:hover{
    color:white;
    background:rgba(255,255,255,.10);
}
.nav-cta{
    background:linear-gradient(135deg,var(--orange),#ff4f1f)!important;
    color:white!important;
    box-shadow:0 12px 28px rgba(255,122,26,.32);
}
.container{
    width:min(1180px,calc(100% - 42px));
    margin:auto;
}
.hero-wrap{padding:56px 0 34px;}
.hero{
    display:grid;
    grid-template-columns:1.08fr .92fr;
    gap:34px;
    align-items:center;
}
.hero-card{
    position:relative;
    overflow:hidden;
    border-radius:34px;
    padding:48px;
    background:linear-gradient(145deg,rgba(255,255,255,.96),rgba(255,255,255,.84));
    border:1px solid rgba(255,255,255,.7);
    box-shadow:0 28px 80px rgba(15,23,42,.14);
}
.hero-kicker{
    display:inline-flex;
    align-items:center;
    gap:9px;
    padding:9px 14px;
    border-radius:999px;
    background:#fff7ed;
    color:#c2410c;
    font-size:13px;
    font-weight:950;
    margin-bottom:20px;
}
.hero h1{
    margin:0;
    font-size:52px;
    line-height:1.02;
    letter-spacing:-2.2px;
    color:#07111f;
}
.gradient-text{
    background:linear-gradient(135deg,#111827,#f97316);
    -webkit-background-clip:text;
    color:transparent;
}
.hero p{
    margin:20px 0 0;
    color:#536176;
    line-height:1.85;
    font-size:17px;
    max-width:670px;
}
.hero-actions{
    margin-top:30px;
    display:flex;
    gap:14px;
    flex-wrap:wrap;
}
.btn{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    gap:9px;
    padding:15px 22px;
    border-radius:16px;
    border:none;
    cursor:pointer;
    font-size:15px;
    font-weight:950;
    transition:.2s;
}
.btn:hover{transform:translateY(-2px);}
.btn-orange{
    background:linear-gradient(135deg,var(--orange),#ff4f1f);
    color:white;
    box-shadow:0 16px 34px rgba(255,122,26,.32);
}
.btn-secondary{
    background:white;
    color:#111827;
    border:1px solid var(--line);
}
.trust-row{
    display:flex;
    flex-wrap:wrap;
    gap:10px;
    margin-top:24px;
}
.pill{
    padding:9px 13px;
    border-radius:999px;
    background:#f1f5f9;
    color:#334155;
    font-size:13px;
    font-weight:900;
}
.showcase{
    border-radius:34px;
    background:#080b17;
    padding:18px;
    box-shadow:0 34px 90px rgba(7,8,18,.34);
    border:1px solid rgba(255,255,255,.08);
}
.showcase-top{
    display:flex;
    gap:7px;
    padding:5px 5px 14px;
}
.dot{
    width:10px;
    height:10px;
    border-radius:50%;
    background:#ef4444;
}
.dot:nth-child(2){background:#f59e0b;}
.dot:nth-child(3){background:#22c55e;}
.showcase-inner{
    height:392px;
    border-radius:24px;
    overflow:hidden;
    position:relative;
    background:
        linear-gradient(90deg,rgba(9,12,24,.72),rgba(249,115,22,.18)),
        url('https://images.unsplash.com/photo-1504674900247-0877df9cc836');
    background-size:cover;
    background-position:center;
}
.showcase-badge{
    position:absolute;
    top:24px;
    right:24px;
    padding:10px 13px;
    border-radius:14px;
    background:rgba(255,255,255,.14);
    color:white;
    backdrop-filter:blur(10px);
    font-size:13px;
    font-weight:900;
}
.showcase-title{
    position:absolute;
    left:30px;
    bottom:30px;
    color:white;
}
.showcase-title h2{
    margin:0;
    font-size:38px;
    line-height:1.02;
    letter-spacing:-1px;
}
.showcase-title p{
    margin:10px 0 0;
    color:rgba(255,255,255,.78);
}
.float-card{
    position:absolute;
    right:24px;
    bottom:26px;
    width:150px;
    padding:14px;
    border-radius:20px;
    background:rgba(255,255,255,.92);
    box-shadow:0 18px 50px rgba(0,0,0,.25);
}
.float-card strong{
    display:block;
    font-size:22px;
}
.float-card span{
    color:#64748b;
    font-size:12px;
    font-weight:800;
}
.section{padding:34px 0;}
.section-head{
    display:flex;
    justify-content:space-between;
    align-items:end;
    gap:20px;
    margin-bottom:22px;
}
.section-head h2{
    margin:0;
    font-size:32px;
    letter-spacing:-1px;
}
.section-head p{
    margin:8px 0 0;
    color:#64748b;
    line-height:1.7;
}
.feature-grid{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:22px;
}
.feature-card{
    background:white;
    border:1px solid rgba(226,232,240,.9);
    border-radius:28px;
    padding:28px;
    box-shadow:0 18px 50px rgba(15,23,42,.08);
    transition:.22s;
}
.feature-card:hover{
    transform:translateY(-5px);
    box-shadow:0 28px 60px rgba(15,23,42,.12);
}
.feature-icon{
    width:54px;
    height:54px;
    border-radius:18px;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:25px;
    margin-bottom:18px;
    background:linear-gradient(135deg,#fff7ed,#ffedd5);
}
.feature-card h3{
    margin:0 0 9px;
    font-size:21px;
}
.feature-card p{
    margin:0;
    color:#64748b;
    line-height:1.7;
}
.steps{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:18px;
}
.step{
    background:linear-gradient(180deg,#fff,#f8fafc);
    border:1px solid #e2e8f0;
    border-radius:24px;
    padding:24px;
}
.step-no{
    width:34px;
    height:34px;
    border-radius:12px;
    background:#111827;
    color:white;
    display:flex;
    align-items:center;
    justify-content:center;
    font-weight:950;
    margin-bottom:14px;
}
.step h3{margin:0 0 8px;}
.step p{
    margin:0;
    color:#64748b;
    line-height:1.65;
}
.page-shell{padding:38px 0 72px;}
.page-title{
    display:flex;
    justify-content:space-between;
    gap:24px;
    align-items:end;
    margin-bottom:24px;
}
.page-title h1{
    margin:0;
    font-size:42px;
    letter-spacing:-1.5px;
}
.page-title p{
    margin:10px 0 0;
    color:#64748b;
    line-height:1.75;
    max-width:650px;
}
.tool-layout{
    display:grid;
    grid-template-columns:430px 1fr;
    gap:28px;
    align-items:start;
}
.panel{
    border-radius:30px;
    background:rgba(255,255,255,.92);
    border:1px solid rgba(226,232,240,.9);
    box-shadow:0 22px 70px rgba(15,23,42,.10);
}
.form-panel{
    padding:0;
    overflow:hidden;
}
.panel-head{
    padding:24px 26px;
    background:linear-gradient(135deg,#111827,#1f2937);
    color:white;
}
.panel-head h2{
    margin:0;
    font-size:22px;
}
.panel-head p{
    margin:8px 0 0;
    color:rgba(255,255,255,.68);
    line-height:1.6;
    font-size:14px;
}
.form-body{padding:26px;}
.tip-box{
    padding:15px;
    border-radius:18px;
    background:#fff7ed;
    border:1px solid #fed7aa;
    color:#9a3412;
    line-height:1.65;
    font-size:14px;
    margin-bottom:20px;
}
.form-group{margin-bottom:17px;}
label{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:10px;
    margin-bottom:8px;
    color:#1e293b;
    font-size:14px;
    font-weight:950;
}
.label-hint{
    color:#94a3b8;
    font-size:12px;
    font-weight:800;
}
input,select{
    width:100%;
    height:48px;
    padding:0 15px;
    border-radius:15px;
    border:1px solid #cbd5e1;
    background:#fff;
    color:#0f172a;
    font-size:15px;
    outline:none;
    transition:.16s;
}
input:focus,select:focus{
    border-color:var(--orange);
    box-shadow:0 0 0 4px rgba(249,115,22,.13);
}
.upload-card{
    border:1px dashed #cbd5e1;
    border-radius:19px;
    background:#f8fafc;
    padding:15px;
}
.upload-card input{background:white;}
.submit-btn{
    width:100%;
    height:54px;
    border:none;
    border-radius:17px;
    cursor:pointer;
    color:white;
    font-size:16px;
    font-weight:950;
    background:linear-gradient(135deg,var(--orange),#ff4f1f);
    box-shadow:0 18px 36px rgba(255,122,26,.28);
}
.submit-btn:hover{transform:translateY(-1px);}
.preview-panel{padding:26px;}
.preview-head{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:18px;
    margin-bottom:18px;
}
.preview-head h2{
    margin:0;
    font-size:22px;
}
.preview-head span{
    color:#94a3b8;
    font-size:13px;
    font-weight:900;
}
.workspace{
    border-radius:24px;
    background:linear-gradient(135deg,#f8fafc,#eef2ff);
    border:1px dashed #cbd5e1;
    min-height:430px;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:26px;
}
.empty-state{
    text-align:center;
    color:#64748b;
}
.empty-icon{
    width:72px;
    height:72px;
    border-radius:24px;
    background:white;
    display:flex;
    align-items:center;
    justify-content:center;
    margin:0 auto 16px;
    font-size:32px;
    box-shadow:0 16px 40px rgba(15,23,42,.08);
}
.empty-state h3{
    margin:0 0 8px;
    font-size:22px;
    color:#334155;
}
.empty-state p{
    margin:0;
    line-height:1.7;
}
.preview-img{
    width:100%;
    display:block;
    border-radius:22px;
    border:1px solid #e2e8f0;
    box-shadow:0 20px 60px rgba(15,23,42,.13);
}
.download-row{
    display:flex;
    flex-wrap:wrap;
    gap:12px;
    margin-top:18px;
}
.download{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    gap:8px;
    padding:13px 18px;
    border-radius:15px;
    font-weight:950;
    background:#111827;
    color:white;
}
.download.secondary{background:#64748b;}
.regen-form{margin-top:15px;}
.regen-btn{
    width:100%;
    height:52px;
    border:none;
    border-radius:16px;
    cursor:pointer;
    background:linear-gradient(135deg,#16a34a,#22c55e);
    color:white;
    font-size:15px;
    font-weight:950;
}
.success{
    padding:15px 16px;
    border-radius:17px;
    background:#ecfdf5;
    color:#166534;
    font-weight:950;
    margin-bottom:16px;
    border:1px solid #bbf7d0;
}
.error{
    padding:15px 16px;
    border-radius:17px;
    background:#fef2f2;
    color:#991b1b;
    font-weight:800;
    margin-bottom:16px;
    border:1px solid #fecaca;
    line-height:1.6;
}
.back{
    display:inline-flex;
    margin-top:18px;
    color:#ea580c;
    font-weight:950;
}
.footer-note{
    margin-top:22px;
    color:#94a3b8;
    font-size:13px;
    line-height:1.6;
}
@media(max-width:980px){
    .hero,
    .tool-layout,
    .feature-grid,
    .steps{
        grid-template-columns:1fr;
    }
    .nav{padding:0 20px;}
    .nav-links{display:none;}
    .hero h1{font-size:40px;}
    .hero-card{padding:34px;}
    .page-title{display:block;}
}

.product-gallery{
    display:grid;
    grid-template-columns:repeat(2,minmax(0,1fr));
    gap:18px;
}
.product-card{
    background:white;
    border:1px solid #e2e8f0;
    border-radius:22px;
    padding:14px;
    box-shadow:0 18px 45px rgba(15,23,42,.08);
}
.product-card img{
    width:100%;
    display:block;
    border-radius:18px;
    border:1px solid #edf2f7;
    background:white;
}
.product-card-title{
    margin:12px 2px 10px;
    color:#334155;
    font-weight:950;
    font-size:14px;
}
.product-card-actions{
    display:flex;
    gap:10px;
    flex-wrap:wrap;
}
.product-card-actions a{
    flex:1;
    min-width:110px;
    text-align:center;
    padding:11px 12px;
    border-radius:13px;
    font-weight:950;
    font-size:13px;
    background:#111827;
    color:white;
}
.product-card-actions a.secondary{
    background:#64748b;
}
.product-mode-grid{
    display:grid;
    grid-template-columns:1fr 1fr;
    gap:12px;
    margin-bottom:18px;
}
.mode-card{
    border:1px solid #e2e8f0;
    background:#f8fafc;
    border-radius:18px;
    padding:14px;
    color:#334155;
    font-size:13px;
    line-height:1.55;
}
.mode-card strong{
    display:block;
    color:#0f172a;
    font-size:15px;
    margin-bottom:4px;
}
@media(max-width:720px){
    .product-gallery,
    .product-mode-grid{
        grid-template-columns:1fr;
    }
}

</style>
"""


def save_upload(file, folder):
    if not file or not file.filename:
        return ""

    ts = str(int(time.time() * 1000))
    filename = ts + "_" + secure_filename(file.filename)
    raw_path = os.path.join(folder, filename)
    file.save(raw_path)

    try:
        img = Image.open(raw_path).convert("RGBA")
        fixed_filename = ts + "_fixed.png"
        fixed_path = os.path.join(folder, fixed_filename)
        img.save(fixed_path, "PNG")

        try:
            os.remove(raw_path)
        except:
            pass

        return fixed_path

    except Exception:
        return raw_path

def resize_to_banner_size(image_path):
    img = Image.open(image_path).convert("RGBA")
    iw, ih = img.size

    target_ratio = BANNER_W / BANNER_H
    img_ratio = iw / ih

    if img_ratio > target_ratio:
        new_h = BANNER_H
        new_w = int(new_h * img_ratio)
    else:
        new_w = BANNER_W
        new_h = int(new_w / img_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - BANNER_W) // 2
    top = (new_h - BANNER_H) // 2

    img = img.crop((left, top, left + BANNER_W, top + BANNER_H))
    img.save(image_path)


def typography_rules():
    return """
AI CREATIVE TYPOGRAPHY DIRECTION:
- GPT Image 2 must generate the text as part of the artwork.
- Keep the assigned text positions and safe area, but make the typography visually designed.
- Text should look like custom premium food advertising lettering, not typed default font.
- Create beautiful campaign typography with strong hierarchy and professional art direction.
- Prioritize design aesthetics, premium food campaign feeling, and brand-advertising impact.

MAIN TITLE:
- Use custom expressive display typography.
- Large, bold, premium, appetizing and memorable.
- For Chinese text, use modern premium Chinese campaign lettering, not default system Chinese font.
- For English text, use custom bold editorial / campaign lettering, not plain Arial-like sans serif.
- Mixed Chinese and English should feel intentionally designed together.
- AI may use elegant letter shaping, tasteful contrast, soft shadow, premium gradient, subtle highlight, layered depth and optical spacing.
- The title should look designed by a senior F&B art director.

SUBTITLE:
- Elegant supporting typography.
- Smaller than the title.
- Premium editorial feeling.
- Can use refined spacing and subtle styling.

BADGE / PRICE / CTA:
- Badge should be an AI-designed premium campaign element, not a simple rectangle.
- Price should have premium advertising price treatment.
- CTA should look like a designed food campaign button if provided.

STYLE REFERENCES:
- GrabFood hero campaign.
- Foodpanda premium restaurant campaign.
- McDonald's modern campaign typography.
- Shake Shack campaign style.
- Modern Korean / Japanese food advertising.
- Apple-like clean hierarchy, but warmer and food-friendly.

AVOID:
- Default fonts.
- Plain bold sans serif.
- Cheap block fonts.
- Ugly PPT-style typography.
- Random messy text.
- Extra words not provided by the user.

IMPORTANT:
- Use only user-provided text.
- Keep text readable.
- Keep text inside its assigned safe area.
- Keep breathing space around text.
"""

def build_prompt(title, subtitle, price, badge, scene):
    rules = []

    if title.strip():
        rules.append(f'Main title placed on the LEFT side, large and readable: "{title}"')

    if subtitle.strip():
        rules.append(f'Subtitle placed below the main title on the LEFT side: "{subtitle}"')

    if price.strip():
        rules.append(f'Price placed near lower-right side of the food only if provided: "{price}"')

    if badge.strip():
        rules.append(f'Promotional badge placed at the BOTTOM-LEFT only if provided: "{badge}"')

    text_rules = "\\n".join(rules)

    return f"""
Create a premium GrabFood / Foodpanda square food poster by editing the uploaded food photo.

Scene:
{SCENES.get(scene, SCENES["auto"])}

FINAL OUTPUT:
- Square 1:1 image.
- Premium commercial food advertising layout.
- Food product should be the hero element and should look large, clear, and appetizing.
- Food product should occupy about 45% to 60% of the poster area.
- Make the food noticeably bigger than a normal background object.
- Do not make the food too small or too zoomed out.
- Do not crop the food.
- Keep the whole food product visible as much as possible.

STRICT POSTER TEMPLATE:
- Main title must be on the LEFT side.
- Subtitle must be below the main title on the LEFT side, only if provided.
- Logo area must stay clean at the TOP-RIGHT.
- Logo will be overlaid later by code. Do not generate logo.
- Badge must be at the BOTTOM-LEFT only if badge text is provided.
- Price must appear only if price text is provided.
- Price should be near the food, lower-right side, clear and readable.
- Do not place food over the title area.
- Do not place food over the logo area.
- Do not place food over the badge area.
- Do not place important objects over the logo area.
- Food should be placed mainly on the RIGHT-CENTER or CENTER-LOWER area.
- Food can be large, but it must not cover the left title area.
- Food can be large, but it must not cover the top-right logo area.
- Food can be large, but it must not cover the bottom-left badge area.

LOGO CLEAN AREA:
- Keep top-right area clean for logo overlay.
- Top-right logo area must contain only simple background or clean negative space.
- Do not place food, plate, bowl, ingredients, smoke, steam, bright objects, text, badge, or decorations in the top-right logo area.
- Do not generate any logo.

OPTIONAL ELEMENT RULE:
- If price is empty, do not show any price, currency, number, discount, or price placeholder.
- If badge is empty, do not show any badge, sticker, label, tag, or placeholder.
- If subtitle is empty, do not show any subtitle or extra small text.
- Use only user provided text.
- Do not invent extra words.
- Do not generate random promo text.

DESIGN STYLE:
- Food should look delicious, premium, sharp, and commercial.
- Strong appetizing food lighting.
- Premium restaurant campaign quality.
- Clean modern layout.
- No watermark.
- No food, plate, bowl, ingredients, garnish, steam, smoke, or bright object inside X 820 to 1080 and Y 0 to 160.
- Keep top-right logo zone clean for overlay.
- No safe area guides.
- No boxes, frames, rulers, dashed lines, or colored guide areas.

{typography_rules()}

USER TEXT:
{text_rules}
"""


def build_banner_prompt(title, subtitle, price, badge, cta, scene):
    rules = []

    has_title = bool(title.strip())
    has_subtitle = bool(subtitle.strip())
    has_price = bool(price.strip())
    has_badge = bool(badge.strip())
    has_cta = bool(cta.strip())

    # ==========================
    # BANNER TEXT POSITION - KEEP ORIGINAL
    # ==========================
    if has_title:
        if has_subtitle:
            rules.append(f'Main headline must be inside safe area, centered around X:270 Y:290: "{title}"')
        else:
            rules.append(f'Main headline must be inside safe area, centered around X:270 Y:345: "{title}"')

    if has_subtitle:
        rules.append(f'Subtitle must be inside safe area, centered around X:270 Y:355: "{subtitle}"')

    if has_badge and has_cta:
        rules.append(f'AI-designed promotional badge must be inside safe area, centered around X:255 Y:480: "{badge}"')
        rules.append(f'CTA button must be inside safe area, centered around X:455 Y:480: "{cta}"')
    elif has_badge and not has_cta:
        rules.append(f'AI-designed promotional badge must be inside safe area, centered around X:255 Y:480: "{badge}"')
    elif has_cta and not has_badge:
        rules.append(f'CTA button must be inside safe area, centered around X:255 Y:480: "{cta}"')

    if has_price:
        rules.append(f'Price text must be inside safe area, centered around X:545 Y:480: "{price}"')

    text_rules = "\\n".join(rules)

    return f"""
Create a premium horizontal food delivery banner by editing the uploaded food photo.

Scene:
{SCENES.get(scene, SCENES["auto"])}

FINAL OUTPUT:
- Final banner must be 1080px wide x 600px tall.
- The full 1080x600 canvas must be filled with one natural premium food advertising background.
- No blurred side padding.
- No duplicated background extension.
- No borders.
- No watermark.

ABSOLUTE SAFE AREA RULE:
- Canvas size: 1080px wide x 600px high.
- TOP DANGER AREA: Y 0 to Y 150.
- SAFE AREA: Y 150 to Y 570.
- BOTTOM DANGER AREA: Y 570 to Y 600.

VERY IMPORTANT:
- ALL text must be inside Y 150 to Y 570.
- ALL title must be inside Y 150 to Y 570.
- ALL subtitle must be inside Y 150 to Y 570.
- ALL badge must be inside Y 150 to Y 570.
- Price must be inside Y 150 to Y 570 only if price is provided.
- ALL CTA must be inside Y 150 to Y 570.
- ALL important food parts must be inside Y 150 to Y 570.
- Logo clean zone must stay at top-right: X 860 to 1060, Y 20 to 140.
- Do not place any important object in Y 0 to Y 150.
- Do not place any important object in Y 570 to Y 600.
- Top 150px must be premium background only.
- Bottom 30px must be premium background only.

STRICT ELEMENT POSITION:
- Food product center: X 760, Y 390.
- If the uploaded food photo is large, zoomed-in, close-up, or cropped, automatically scale the food smaller before composing the banner.
- Food must stay mainly inside safe area.
- Main title center: X 270, Y 290 if subtitle exists.
- Main title center: X 270, Y 345 if subtitle does not exist.
- Subtitle center: X 270, Y 355.
- If badge only: Badge center X 255, Y 480.
- If CTA only: CTA center X 255, Y 480.
- If badge and CTA both exist: Badge center X 255, Y 480, CTA center X 455, Y 480.
- If price exists: Price center X 545, Y 480.
- If price is empty: no price, no price tag, no currency, no price placeholder.
- Logo clean zone: X 860 to 1060, Y 20 to 140.

BACKGROUND ART DIRECTION:
- Create a realistic full-canvas premium restaurant / delivery campaign background.
- Background must look intentional, not AI-random.
- Use depth, soft bokeh, warm appetizing lighting, gentle table surface, and realistic shadows.
- Left side behind title must be cleaner and less busy for readability.
- Right side can have richer food atmosphere but must not enter the logo clean zone.
- Avoid messy props.
- Avoid random ingredients flying around.
- Avoid fake labels, fake packaging, fake words, fake signs, fake brand marks.
- No artificial colored blocks, no safe area boxes, no guide lines.

FOOD COMPOSITION IMPROVEMENT:
- Food should be appetizing, premium and realistic.
- Food should occupy about 30% to 38% of banner width.
- Food must be the visual hero, but not too zoomed in.
- Keep the full food product visible as much as possible.
- Do not crop the plate, bowl, box, cup, or important food parts.
- Food product center should stay around X 760, Y 390.
- Food can overlap natural background shadow only, not text elements.
- Food must not cover title, subtitle, badge, price, CTA, or logo zone.
- Food must stay away from the top-right logo clean zone.
- Food must not enter X 820 to 1080 and Y 0 to 160.
- No food, plate, bowl, ingredients, sauce, steam, smoke, garnish, or bright object may appear inside the logo zone.
- Do not place food in top danger area.
- Do not place food in bottom danger area.

FOOD QUALITY:
- Preserve the identity of the uploaded food.
- Improve lighting, sharpness, plating feel and commercial appeal.
- Make the food look more delicious, but do not transform it into another dish.
- Add natural contact shadow under the food.
- Add very subtle steam only when suitable.
- Avoid plastic-looking food.
- Avoid over-saturated colors.
- Avoid unrealistic melted textures.

LOGO CLEAN ZONE:
- Logo will be overlaid later by code.
- Logo final position is TOP-RIGHT CORNER.
- Keep X 860 to 1060 and Y 20 to 140 completely clean.
- Maintain clean negative space for the logo.
- Background in this zone should remain simple, dark/bright enough, and not busy.
- Do not generate logo.
- No food, no bowl, no plate, no ingredients, no smoke, no steam, no bright objects, no text, no badge, no price, no CTA, no decoration in this zone.

TEXT AND OPTIONAL ELEMENT RULE:
- Only generate elements that have user-provided text under USER TEXT.
- Use ONLY the exact user-provided text.
- Do not invent extra words.
- Do not invent promo text.
- Do not generate fake food delivery platform text.

PRICE RULE:
- If price text is provided, show the exact price text at X 545 Y 480.
- If price text is empty, do NOT generate any price element.
- If price text is empty, do NOT generate currency, RM, $, %, discount, sale amount, number, price tag, price sticker, price badge, price label, empty price box, empty price placeholder, or decorative shape that looks like a price area.

BADGE RULE:
- If badge text is provided and CTA is empty, show badge at X 255 Y 480.
- If badge text is provided and CTA is also provided, show badge at X 255 Y 480 and CTA at X 455 Y 480.
- If badge text is empty, do NOT generate any badge, sticker, label, promotion tag, ribbon, stamp, or badge placeholder.

CTA RULE:
- If CTA text is provided and badge is empty, show CTA at X 255 Y 480.
- If CTA text is provided and badge is also provided, show CTA at X 455 Y 480.
- If CTA text is empty, do NOT generate any CTA button, button shape, order button, "Order Now", "Buy Now", "Shop Now", or CTA placeholder.

SUBTITLE RULE:
- If subtitle text is empty, do NOT generate any subtitle, small caption, tagline, slogan, or secondary text.

TYPOGRAPHY STYLE:
- Keep the banner text behavior and text placement unchanged.
- GPT Image 2 should generate the text as premium custom advertising lettering.
- Do not use default fonts or plain typed-looking text.
- Main headline should look like custom-designed F&B campaign typography.
- Typography can be expressive, elegant, bold, layered and premium.
- AI may design beautiful title lettering, badge shape, price style and CTA button.
- Prioritize aesthetics, campaign feeling and visual impact while keeping readability.
- Chinese text must look like premium modern Chinese campaign lettering, not generic system font.
- English text must look like premium editorial / food campaign display typography.
- Badge must look designed, not like a simple rectangle.
- Price must look like a premium price treatment, not plain text.
- CTA must look like a polished food campaign button.
- No messy text.
- No random text.

NEGATIVE PROMPT:
- No text above Y 150.
- No badge above Y 150.
- No price above Y 150.
- No CTA above Y 150.
- No important food part above Y 150.
- No text below Y 570.
- No badge below Y 570.
- No price below Y 570.
- No CTA below Y 570.
- No important food part below Y 570.
- No safe area guide lines.
- No colored guide boxes.
- No watermark.
- No fake brand logo.
- No fake delivery platform UI.
- No random labels.
- No random words.
- No duplicated food unless the uploaded product naturally contains multiple items.
- No food, plate, bowl, ingredients, garnish, steam, smoke, or bright object inside X 820 to 1080 and Y 0 to 160.
- Keep top-right logo zone clean for overlay.

TEXT EXISTENCE CHECK:
- Render ONLY elements listed under USER TEXT.
- If price is not listed under USER TEXT, price must not appear visually at all.
- If badge is not listed under USER TEXT, badge must not appear visually at all.
- If CTA is not listed under USER TEXT, CTA must not appear visually at all.
- If subtitle is not listed under USER TEXT, subtitle must not appear visually at all.
- Do not create empty placeholders.
- Do not create decorative shapes that look like missing badges, price tags, or CTA buttons.

USER TEXT:
{text_rules}
"""

def overlay_logo(poster_path, logo_path):
    if not logo_path or not os.path.exists(logo_path):
        return

    poster = Image.open(poster_path).convert("RGBA")
    logo = Image.open(logo_path).convert("RGBA")

    pw, ph = poster.size
    max_w = int(pw * 0.26)
    max_h = int(ph * 0.14)

    lw, lh = logo.size
    scale = min(max_w / lw, max_h / lh)

    nw = int(lw * scale)
    nh = int(lh * scale)

    logo = logo.resize((nw, nh), Image.LANCZOS)

    x = pw - nw - int(pw * 0.05)
    y = int(ph * 0.04)

    poster.alpha_composite(logo, (x, y))
    poster.save(poster_path)


def overlay_banner_logo(banner_path, logo_path):
    if not logo_path or not os.path.exists(logo_path):
        return

    banner = Image.open(banner_path).convert("RGBA")
    logo = Image.open(logo_path).convert("RGBA")

    bw, bh = banner.size

    # Banner logo size: professional top-right placement
    max_w = 180
    max_h = 90

    lw, lh = logo.size
    scale = min(max_w / lw, max_h / lh)

    nw = int(lw * scale)
    nh = int(lh * scale)

    logo = logo.resize((nw, nh), Image.LANCZOS)

    # True top-right corner position
    margin_right = 36
    margin_top = 28

    x = bw - nw - margin_right
    y = margin_top

    banner.alpha_composite(logo, (x, y))
    banner.save(banner_path)


def generate_poster_image(image_path, logo_path, title, subtitle, price, badge, scene):
    prompt = build_prompt(title, subtitle, price, badge, scene)

    with open(image_path, "rb") as img:
        result = get_openai_client().images.edit(
            model=IMAGE_MODEL,
            image=[img],
            prompt=prompt,
            size="1024x1024"
        )

    image_bytes = base64.b64decode(result.data[0].b64_json)

    output_filename = str(int(time.time() * 1000)) + "_poster.png"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    overlay_logo(output_path, logo_path)
    return output_filename


def generate_banner_image(image_path, logo_path, title, subtitle, price, badge, cta, scene):
    prompt = build_banner_prompt(title, subtitle, price, badge, cta, scene)

    with open(image_path, "rb") as img:
        result = get_openai_client().images.edit(
            model=IMAGE_MODEL,
            image=[img],
            prompt=prompt,
            size="1536x1024"
        )

    image_bytes = base64.b64decode(result.data[0].b64_json)

    output_filename = str(int(time.time() * 1000)) + "_banner_1080x600.png"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    resize_to_banner_size(output_path)
    overlay_banner_logo(output_path, logo_path)

    return output_filename



def resize_to_product_size(image_path):
    img = Image.open(image_path).convert("RGBA")
    img = img.resize((PRODUCT_W, PRODUCT_H), Image.LANCZOS)
    img.save(image_path)


def build_product_prompt(has_drink=False, has_side=False):
    bundle_rules = []

    if has_drink and has_side:
        bundle_rules.append("- There are three uploaded images: main product, drink and side snack.")
        bundle_rules.append("- Main product must be the largest object, placed in the front center.")
        bundle_rules.append("- Drink and side snack must be placed behind the main product as supporting bundle items.")
        bundle_rules.append("- Drink should be behind-left or behind-right, side snack should balance the opposite side.")
    elif has_drink:
        bundle_rules.append("- There are two uploaded images: main product and drink.")
        bundle_rules.append("- Main product must be the largest object, placed in the front center.")
        bundle_rules.append("- Drink must be behind the main product as a supporting bundle item.")
    elif has_side:
        bundle_rules.append("- There are two uploaded images: main product and side snack.")
        bundle_rules.append("- Main product must be the largest object, placed in the front center.")
        bundle_rules.append("- Side snack must be behind the main product as a supporting bundle item.")
    else:
        bundle_rules.append("- There is only one uploaded image: main product.")
        bundle_rules.append("- Show only the main product, centered and premium.")

    bundle_text = "\n".join(bundle_rules)

    return f"""
Create a premium clean food product image by editing the uploaded food photo or photos.

FINAL OUTPUT:
- Square 1:1 product image.
- Final image must look like a professional menu / ecommerce product photo.
- White background only.
- No text.
- No logo.
- No price.
- No badge.
- No border.
- No watermark.

CANVAS:
- 1080px x 1080px final target.
- Clean pure white background (#FFFFFF).
- Product should be fully visible.
- Do not crop the plate, bowl, cup, packaging, or food.

PRODUCT DETECTION:
- Automatically detect the main food product from the first uploaded image.
- Keep the real food identity, ingredients, shape, color and texture.
- Improve lighting and presentation, but do not change the dish into a different food.
- Remove messy original background.
- Do not add extra food that was not uploaded.

BUNDLE COMPOSITION:
{bundle_text}

LAYOUT:
- Main product should occupy about 66% to 78% of the image area.
- Supporting optional products should occupy about 20% to 30% each.
- Supporting products must stay behind the main product and must not overpower it.
- Main product should be visually dominant.
- Keep natural realistic spacing.
- Use a slight front angle or natural menu product angle.
- Leave clean white margin around the full product.

SHADOW AND DEPTH:
- Add a soft natural light grey contact shadow under each item.
- Shadow should be subtle, premium and realistic.
- Do not use harsh black shadows.
- Product must feel grounded on a clean studio surface.

FOOD QUALITY:
- Premium commercial food photography.
- Bright clean studio lighting.
- Appetizing, sharp, high quality.
- Preserve natural food texture.
- Avoid plastic-looking food.
- Avoid over-smoothing.
- Avoid over-saturated colors.
- Suitable for GrabFood, Foodpanda, menu, ecommerce and POS product listing.

FRESH HOT FOOD FEEL:
- Add very subtle steam above hot food if suitable.
- Steam must be light, elegant and realistic.
- Do not overdo smoke.
- No messy fog.

STRICT NEGATIVE RULES:
- No text.
- No random words.
- No logo.
- No price.
- No badge.
- No hands.
- No people.
- No table scene.
- No kitchen scene.
- No colored background.
- No props unless they are part of the uploaded product.
- No extra food that was not uploaded.
- No duplicated products unless necessary for realistic composition.
- No cropped product.
"""

def generate_product_image(main_path, drink_path="", side_path=""):
    prompt = build_product_prompt(
        has_drink=bool(drink_path and os.path.exists(drink_path)),
        has_side=bool(side_path and os.path.exists(side_path))
    )

    image_files = []
    try:
        image_files.append(open(main_path, "rb"))

        if drink_path and os.path.exists(drink_path):
            image_files.append(open(drink_path, "rb"))

        if side_path and os.path.exists(side_path):
            image_files.append(open(side_path, "rb"))

        result = get_openai_client().images.edit(
            model=IMAGE_MODEL,
            image=image_files,
            prompt=prompt,
            size="1024x1024"
        )
    finally:
        for f in image_files:
            try:
                f.close()
            except Exception:
                pass

    image_bytes = base64.b64decode(result.data[0].b64_json)

    output_filename = str(int(time.time() * 1000)) + "_product_1080x1080.png"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    resize_to_product_size(output_path)
    return output_filename


def generate_batch_product_images(main_paths, drink_path="", side_path=""):
    results = []

    for index, main_path in enumerate(main_paths, start=1):
        filename = generate_product_image(main_path, drink_path, side_path)
        results.append({
            "index": index,
            "filename": filename
        })

    return results

def render_nav():
    return """
<div class="nav">
    <a class="brand" href="/">
        <div class="logo-mark">AI</div>
        <div>Food Ad Studio</div>
    </a>
    <div class="nav-links">
        <a href="/">Home</a>
        <a href="/poster">头图</a>
        <a href="/banner">Banner</a>
        <a href="/product">产品图</a>
        <a class="nav-cta" href="/banner">Create Now</a>
    </div>
</div>
"""


def scene_options(scene):
    return f"""
<option value="auto" {"selected" if scene == "auto" else ""}>Auto 智能场景</option>
<option value="plain" {"selected" if scene == "plain" else ""}>Plain 简约背景</option>
<option value="kitchen" {"selected" if scene == "kitchen" else ""}>Kitchen 餐厅厨房</option>
<option value="japanese" {"selected" if scene == "japanese" else ""}>Japanese 日式氛围</option>
<option value="hawker" {"selected" if scene == "hawker" else ""}>Hawker 马来西亚档口</option>
<option value="luxury" {"selected" if scene == "luxury" else ""}>Luxury 高级暗调</option>
"""


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/poster", methods=["GET", "POST"])
def poster():
    title = ""
    subtitle = ""
    price = ""
    badge = ""
    scene = "auto"
    result_filename = ""
    error = ""
    image_path = ""
    logo_path = ""

    if request.method == "POST":
        title = request.form.get("title", "")
        subtitle = request.form.get("subtitle", "")
        price = request.form.get("price", "")
        badge = request.form.get("badge", "")
        scene = request.form.get("scene", "auto")

        image_path = request.form.get("image_path", "")
        logo_path = request.form.get("logo_path", "")

        main_photo = request.files.get("food")
        logo_file = request.files.get("logo")

        if main_photo and main_photo.filename:
            image_path = save_upload(main_photo, UPLOAD_FOLDER)

        if logo_file and logo_file.filename:
            logo_path = save_upload(logo_file, LOGO_FOLDER)

        if not image_path or not os.path.exists(image_path):
            error = "Please upload food photo."

        if not error:
            try:
                result_filename = generate_poster_image(
                    image_path, logo_path, title, subtitle, price, badge, scene
                )
            except Exception as e:
                error = str(e)

    error_html = f'<div class="error"><b>生成失败：</b><br>{error}</div>' if error else ""

    result_html = """
    <div class="workspace">
        <div class="empty-state">
            <div class="empty-icon">🍱</div>
            <h3>等待生成头图</h3>
            <p>上传食物图并填写资料后，AI 结果会显示在这里。</p>
        </div>
    </div>
    """

    if result_filename:
        result_html = f"""
        <div class="success">✅ 头图生成成功！</div>
        <img src="/outputs/{result_filename}" class="preview-img">

        <div class="download-row">
            <a class="download" href="/download/{result_filename}">⬇ 下载 PNG</a>
            <a class="download secondary" href="/outputs/{result_filename}" target="_blank">👁 查看原图</a>
        </div>

        <form method="POST" enctype="multipart/form-data" class="regen-form">
            <input type="hidden" name="image_path" value="{image_path}">
            <input type="hidden" name="logo_path" value="{logo_path}">
            <input type="hidden" name="title" value="{title}">
            <input type="hidden" name="subtitle" value="{subtitle}">
            <input type="hidden" name="price" value="{price}">
            <input type="hidden" name="badge" value="{badge}">
            <input type="hidden" name="scene" value="{scene}">
            <button class="regen-btn">🔄 用一样资料重新生成</button>
        </form>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>头图生成 - Food Ad Studio</title>
{BASE_CSS}
</head>
<body>
{render_nav()}

<div class="container page-shell">
    <div class="page-title">
        <div>
            <div class="hero-kicker">🍱 Poster Generator</div>
            <h1>头图生成</h1>
            <p>上传食物图，填写标题、价格和促销内容，AI 会自动生成专业外卖头图。</p>
        </div>
    </div>

    <div class="tool-layout">
        <div class="panel form-panel">
            <div class="panel-head">
                <h2>广告内容</h2>
                <p>填写你想显示在图片上的资料，不需要的项目可以留空。</p>
            </div>

            <div class="form-body">
                <div class="tip-box">
                    价格、Badge、副标题都是可选内容，没填写就不会出现在图片里。
                </div>

                {error_html}

                <form method="POST" enctype="multipart/form-data">
                    <div class="form-group">
                        <label>上传食物图 <span class="label-hint">Required</span></label>
                        <div class="upload-card">
                            <input type="file" name="food" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>上传 Logo <span class="label-hint">Optional</span></label>
                        <div class="upload-card">
                            <input type="file" name="logo">
                        </div>
                    </div>

                    <div class="form-group">
                        <label>主标题 / Title</label>
                        <input name="title" value="{title}" placeholder="香辣炸鸡饭">
                    </div>

                    <div class="form-group">
                        <label>副标题 / Subtitle <span class="label-hint">Optional</span></label>
                        <input name="subtitle" value="{subtitle}" placeholder="招牌热卖">
                    </div>

                    <div class="form-group">
                        <label>价格 / Price <span class="label-hint">Optional</span></label>
                        <input name="price" value="{price}" placeholder="RM12.90">
                    </div>

                    <div class="form-group">
                        <label>Badge <span class="label-hint">Optional</span></label>
                        <input name="badge" value="{badge}" placeholder="BEST SELLER">
                    </div>

                    <div class="form-group">
                        <label>场景</label>
                        <select name="scene">
                            {scene_options(scene)}
                        </select>
                    </div>

                    <button class="submit-btn">生成头图</button>
                </form>

                <a class="back" href="/">← 返回首页</a>
                <div class="footer-note">生成效果可能会因食物图质量、标题长度和场景选择而变化。</div>
            </div>
        </div>

        <div class="panel preview-panel">
            <div class="preview-head">
                <h2>生成预览</h2>
                <span>Preview</span>
            </div>
            {result_html}
        </div>
    </div>
</div>
</body>
</html>
"""


@app.route("/banner", methods=["GET", "POST"])
def banner():
    title = ""
    subtitle = ""
    price = ""
    badge = ""
    cta = ""
    scene = "auto"
    result_filename = ""
    error = ""
    image_path = ""
    logo_path = ""

    if request.method == "POST":
        title = request.form.get("title", "")
        subtitle = request.form.get("subtitle", "")
        price = request.form.get("price", "")
        badge = request.form.get("badge", "")
        cta = request.form.get("cta", "")
        scene = request.form.get("scene", "auto")

        image_path = request.form.get("image_path", "")
        logo_path = request.form.get("logo_path", "")

        main_photo = request.files.get("food")
        logo_file = request.files.get("logo")

        if main_photo and main_photo.filename:
            image_path = save_upload(main_photo, UPLOAD_FOLDER)

        if logo_file and logo_file.filename:
            logo_path = save_upload(logo_file, LOGO_FOLDER)

        if not image_path or not os.path.exists(image_path):
            error = "Please upload food photo."

        if not error:
            try:
                result_filename = generate_banner_image(
                    image_path, logo_path, title, subtitle, price, badge, cta, scene
                )
            except Exception as e:
                error = str(e)

    error_html = f'<div class="error"><b>生成失败：</b><br>{error}</div>' if error else ""

    result_html = """
    <div class="workspace">
        <div class="empty-state">
            <div class="empty-icon">🖼️</div>
            <h3>等待生成 Banner</h3>
            <p>上传食物图并填写资料后，AI Banner 会显示在这里。</p>
        </div>
    </div>
    """

    if result_filename:
        result_html = f"""
        <div class="success">✅ Banner 生成成功！</div>
        <img src="/outputs/{result_filename}" class="preview-img">

        <div class="download-row">
            <a class="download" href="/download/{result_filename}">⬇ 下载 Banner PNG</a>
            <a class="download secondary" href="/outputs/{result_filename}" target="_blank">👁 查看原图</a>
        </div>

        <form method="POST" enctype="multipart/form-data" class="regen-form">
            <input type="hidden" name="image_path" value="{image_path}">
            <input type="hidden" name="logo_path" value="{logo_path}">
            <input type="hidden" name="title" value="{title}">
            <input type="hidden" name="subtitle" value="{subtitle}">
            <input type="hidden" name="price" value="{price}">
            <input type="hidden" name="badge" value="{badge}">
            <input type="hidden" name="cta" value="{cta}">
            <input type="hidden" name="scene" value="{scene}">
            <button class="regen-btn">🔄 用一样资料重新生成 Banner</button>
        </form>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>Banner 生成 - Food Ad Studio</title>
{BASE_CSS}
</head>
<body>
{render_nav()}

<div class="container page-shell">
    <div class="page-title">
        <div>
            <div class="hero-kicker">🖼️ Banner Generator</div>
            <h1>外卖 Banner 生成</h1>
            <p>上传食物图，填写标题、价格和促销内容，AI 会自动生成专业外卖 Banner。</p>
        </div>
    </div>

    <div class="tool-layout">
        <div class="panel form-panel">
            <div class="panel-head">
                <h2>Banner 内容</h2>
                <p>输入广告内容后，AI 会自动完成画面设计和排版。</p>
            </div>

            <div class="form-body">
                <div class="tip-box">
                    副标题、价格、Badge 和 CTA 都是可选内容，不填写就不会出现在图片里。
                </div>

                {error_html}

                <form method="POST" enctype="multipart/form-data">
                    <div class="form-group">
                        <label>上传食物图 <span class="label-hint">Required</span></label>
                        <div class="upload-card">
                            <input type="file" name="food" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>上传 Logo <span class="label-hint">Optional</span></label>
                        <div class="upload-card">
                            <input type="file" name="logo">
                        </div>
                    </div>

                    <div class="form-group">
                        <label>主标题 / Headline</label>
                        <input name="title" value="{title}" placeholder="香辣炸鸡饭">
                    </div>

                    <div class="form-group">
                        <label>副标题 / Subtitle <span class="label-hint">Optional</span></label>
                        <input name="subtitle" value="{subtitle}" placeholder="今日限定优惠">
                    </div>

                    <div class="form-group">
                        <label>价格 / Price <span class="label-hint">Optional</span></label>
                        <input name="price" value="{price}" placeholder="RM12.90">
                    </div>

                    <div class="form-group">
                        <label>Badge <span class="label-hint">Optional</span></label>
                        <input name="badge" value="{badge}" placeholder="BEST SELLER">
                    </div>

                    <div class="form-group">
                        <label>CTA 按钮文字 <span class="label-hint">Optional</span></label>
                        <input name="cta" value="{cta}" placeholder="Order Now">
                    </div>

                    <div class="form-group">
                        <label>场景</label>
                        <select name="scene">
                            {scene_options(scene)}
                        </select>
                    </div>

                    <button class="submit-btn">生成 Banner</button>
                </form>

                <a class="back" href="/">← 返回首页</a>
                <div class="footer-note">建议上传清晰、光线好的食物图，生成效果会更接近商业摄影。</div>
            </div>
        </div>

        <div class="panel preview-panel">
            <div class="preview-head">
                <h2>生成预览</h2>
                <span>Preview</span>
            </div>
            {result_html}
        </div>
    </div>
</div>
</body>
</html>
"""

@app.route("/generate", methods=["POST"])
def generate():
    try:
        title = request.form.get("title", "")
        subtitle = request.form.get("subtitle", "")
        price = request.form.get("price", "")
        badge = request.form.get("badge", "")
        scene = request.form.get("style", "auto")
        size = request.form.get("size", "1080x600")

        main_photo = request.files.get("food_image")
        logo_file = request.files.get("logo")

        if not main_photo or not main_photo.filename:
            return jsonify({
                "success": False,
                "error": "Please upload food image."
            }), 400

        image_path = save_upload(main_photo, UPLOAD_FOLDER)

        logo_path = ""
        if logo_file and logo_file.filename:
            logo_path = save_upload(logo_file, LOGO_FOLDER)

        if size == "1080x1080":
            filename = generate_poster_image(
                image_path,
                logo_path,
                title,
                subtitle,
                price,
                badge,
                scene
            )
        else:
            filename = generate_banner_image(
                image_path,
                logo_path,
                title,
                subtitle,
                price,
                badge,
                "",
                scene
            )

        return jsonify({
            "success": True,
            "image_url": f"/outputs/{filename}"
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/outputs/<filename>")
def outputs(filename):
    return send_file(os.path.join(OUTPUT_FOLDER, filename))


@app.route("/download/<filename>")
def download(filename):
    path = os.path.join(OUTPUT_FOLDER, filename)

    return send_file(
        path,
        as_attachment=True,
        download_name=filename
    )



@app.route("/product", methods=["GET", "POST"])
def product():
    error = ""
    result_files = []
    drink_path = ""
    side_path = ""

    if request.method == "POST":
        main_files = request.files.getlist("main_products")
        drink_file = request.files.get("drink")
        side_file = request.files.get("side")

        main_paths = []

        for file in main_files:
            if file and file.filename:
                main_paths.append(save_upload(file, UPLOAD_FOLDER))

        if drink_file and drink_file.filename:
            drink_path = save_upload(drink_file, UPLOAD_FOLDER)

        if side_file and side_file.filename:
            side_path = save_upload(side_file, UPLOAD_FOLDER)

        if not main_paths:
            error = "Please upload at least one main product photo."

        if not error:
            try:
                result_files = generate_batch_product_images(
                    main_paths,
                    drink_path,
                    side_path
                )
            except Exception as e:
                error = str(e)

    error_html = f'<div class="error"><b>生成失败：</b><br>{error}</div>' if error else ""

    result_html = """
    <div class="workspace">
        <div class="empty-state">
            <div class="empty-icon">✨</div>
            <h3>等待生成产品图</h3>
            <p>上传主产品图片，可选饮料或小吃后，AI 会生成白底产品图。</p>
        </div>
    </div>
    """

    if result_files:
        cards = ""
        for item in result_files:
            filename = item["filename"]
            index = item["index"]
            cards += f"""
            <div class="product-card">
                <img src="/outputs/{filename}">
                <div class="product-card-title">产品图 {index}</div>
                <div class="product-card-actions">
                    <a href="/download/{filename}">⬇ 下载</a>
                    <a class="secondary" href="/outputs/{filename}" target="_blank">👁 查看</a>
                </div>
            </div>
            """

        result_html = f"""
        <div class="success">✅ 已生成 {len(result_files)} 张产品图！</div>
        <div class="product-gallery">
            {cards}
        </div>
        """

    return f"""
<!DOCTYPE html>
<html>
<head>
<title>产品图生成 - Food Ad Studio</title>
{BASE_CSS}
</head>
<body>
{render_nav()}

<div class="container page-shell">
    <div class="page-title">
        <div>
            <div class="hero-kicker">✨ Product Image Generator</div>
            <h1>白底产品图生成</h1>
            <p>
                批量上传主产品图，AI 自动侦测食物并生成 1080 × 1080 白底产品图。
                饮料和小吃都是可选，可组合成 Bundle 产品图。
            </p>
        </div>
    </div>

    <div class="tool-layout">
        <div class="panel form-panel">
            <div class="panel-head">
                <h2>产品图内容</h2>
                <p>主产品必选，饮料和小吃可选。可以一次上传多张主产品批量生成。</p>
            </div>

            <div class="form-body">
                <div class="tip-box">
                    输出规格：白色背景、浅阴影、轻微热气、1:1 比例、1080 × 1080px。不会加入文字、价格、Logo 或 Badge。
                </div>

                <div class="product-mode-grid">
                    <div class="mode-card">
                        <strong>单品模式</strong>
                        只上传主产品，系统生成干净白底单品图。
                    </div>
                    <div class="mode-card">
                        <strong>Bundle 模式</strong>
                        上传饮料或小吃，系统会放在主产品后面衬托。
                    </div>
                </div>

                {error_html}

                <form method="POST" enctype="multipart/form-data">
                    <div class="form-group">
                        <label>上传主产品图 <span class="label-hint">Required / 可多选</span></label>
                        <div class="upload-card">
                            <input type="file" name="main_products" multiple required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label>上传饮料 <span class="label-hint">Optional</span></label>
                        <div class="upload-card">
                            <input type="file" name="drink">
                        </div>
                    </div>

                    <div class="form-group">
                        <label>上传小吃 / 配菜 <span class="label-hint">Optional</span></label>
                        <div class="upload-card">
                            <input type="file" name="side">
                        </div>
                    </div>

                    <button class="submit-btn">生成产品图</button>
                </form>

                <a class="back" href="/">← 返回首页</a>
                <div class="footer-note">
                    建议上传清晰、主体完整、光线足够的食物图。批量图片越多，生成时间越长。
                </div>
            </div>
        </div>

        <div class="panel preview-panel">
            <div class="preview-head">
                <h2>生成结果</h2>
                <span>Gallery</span>
            </div>
            {result_html}
        </div>
    </div>
</div>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)