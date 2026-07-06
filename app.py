import os
import time
import base64
import io
import zipfile
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from openai import OpenAI
from PIL import Image, ImageFilter, ImageStat
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

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = (
    os.getenv("SUPABASE_ANON_KEY")
    or os.getenv("SUPABASE_PUBLISHABLE_KEY")
    or ""
)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "generated-images")

IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

# Final output sizes
BANNER_W = 1080
BANNER_H = 600

POSTER_W = 1080
POSTER_H = 1080

PRODUCT_W = 720
PRODUCT_H = 720

SOCIAL_OUTPUTS = {
    "feed": {"label": "Instagram Feed", "width": 1080, "height": 1080, "openai_size": "1024x1024", "resize": "exact"},
    "portrait": {"label": "Portrait Post", "width": 1080, "height": 1350, "openai_size": "1024x1536", "resize": "cover"},
    "story": {"label": "Story / Status", "width": 1080, "height": 1920, "openai_size": "1024x1536", "resize": "cover"},
    "facebook_ad": {"label": "Facebook Ad", "width": 1200, "height": 628, "openai_size": "1536x1024", "resize": "cover"},
}

VISUAL_OUTPUTS = {
    "product": {"label": "Platform Product Photo", "width": PRODUCT_W, "height": PRODUCT_H},
    "poster": {"label": "Square Promo Poster", "width": POSTER_W, "height": POSTER_H},
    "banner": {"label": "Delivery Banner", "width": BANNER_W, "height": BANNER_H},
}

PLATFORM_PACKS = {
    "single": {
        "label": "Single Output",
        "types": [],
        "description": "Generate the selected output only.",
    },
    "grabfood_menu": {
        "label": "GrabFood Menu Ready",
        "types": ["product", "banner"],
        "description": "Product photo plus a 9:5 style delivery banner for GrabFood storefront usage.",
    },
    "foodpanda_menu": {
        "label": "foodpanda Menu Ready",
        "types": ["product", "poster"],
        "description": "Clean menu product photo plus square promo creative for foodpanda and menu campaigns.",
    },
    "malaysia_starter": {
        "label": "Malaysia Starter Kit",
        "types": ["product", "banner", "poster"],
        "description": "A complete first delivery pack for Malaysian restaurant owners.",
    },
}

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

def get_or_create_profile(user_id: str, email: str):
    """
    Trial model:
    - trial users get 10 total generations
    - trial expires 2 days after first profile creation
    - pro users bypass trial limits
    """
    if not user_id or not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None

    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/profiles",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            },
            params={
                "id": f"eq.{user_id}",
                "select": "*",
                "limit": "1",
            },
            timeout=30,
        )

        data = r.json() if r.status_code == 200 else []

        if data:
            return data[0]

        create_response = requests.post(
            f"{SUPABASE_URL}/rest/v1/profiles",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json={
                "id": user_id,
                "email": email,
                "plan": "trial",
                "trial_limit": 10,
                "trial_used": 0,
            },
            timeout=30,
        )

        if create_response.status_code in (200, 201):
            created = create_response.json()
            if created:
                return created[0]

        return {
            "id": user_id,
            "email": email,
            "plan": "trial",
            "trial_limit": 10,
            "trial_used": 0,
        }

    except Exception as e:
        print("Profile load/create error:", e)
        return None


def check_generation_limit(user_id: str, email: str):
    """
    Returns: (allowed: bool, profile: dict, reason: str)
    """
    profile = get_or_create_profile(user_id, email)

    if not profile:
        # If profile cannot be loaded, allow generation rather than blocking paying users by mistake.
        return True, None, ""

    plan = (profile.get("plan") or "trial").lower()

    if plan == "pro":
        return True, profile, ""

    trial_limit = int(profile.get("trial_limit") or 10)
    trial_used = int(profile.get("trial_used") or 0)
    trial_expired = bool(profile.get("trial_expired"))

    if trial_expired:
        return False, profile, "trial_expired"

    if trial_used >= trial_limit:
        return False, profile, "trial_exhausted"

    return True, profile, ""


def increment_usage(user_id: str):
    if not user_id or not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return

    try:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/increment_trial_usage",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
            },
            json={"user_id_input": user_id},
            timeout=30,
        )

        if response.status_code not in (200, 204):
            print("Usage increment failed:", response.status_code, response.text)

    except Exception as e:
        print("Usage increment error:", e)



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


def overlay_logo(image_path: str, logo_path: str, visual_type: str, hotdeal_safe_zone: bool = False) -> None:
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
        elif hotdeal_safe_zone:
            max_w = int(bw * 0.12)
            max_h = int(bh * 0.08)
            margin_right = int(bw * 0.02)
            margin_top = int(bh * 0.04)
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


def upload_to_supabase_storage(local_path: str, storage_key: str) -> Optional[str]:
    """
    Upload a generated PNG to Supabase Storage and return the public URL.
    The bucket should be public. Default bucket: generated-images.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("Storage skipped: missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return None

    try:
        with open(local_path, "rb") as f:
            response = requests.post(
                f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_STORAGE_BUCKET}/{storage_key}",
                headers={
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                    "apikey": SUPABASE_SERVICE_KEY,
                    "Content-Type": "image/png",
                    "x-upsert": "true",
                },
                data=f,
                timeout=120,
            )

        if response.status_code not in (200, 201):
            print("Supabase storage upload failed:", response.status_code, response.text)
            return None

        return f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_STORAGE_BUCKET}/{storage_key}"

    except Exception as e:
        print("Supabase storage upload error:", e)
        return None


def save_design_to_supabase(
    user_id: str,
    user_email: str,
    image_url: str,
    download_url: str,
    visual_type: str,
    title: str,
) -> None:
    """
    Save a generated design record into public.designs.
    Requires a designs table in Supabase and SUPABASE_SERVICE_ROLE_KEY in Railway.
    """
    if not user_id:
        return

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("Design save skipped: missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return

    try:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/designs",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={
                "user_id": user_id,
                "user_email": user_email,
                "image_url": image_url,
                "download_url": download_url,
                "visual_type": visual_type,
                "title": title,
            },
            timeout=30,
        )

        if response.status_code not in (200, 201, 204):
            print("Design save failed:", response.status_code, response.text)

    except Exception as e:
        print("Design save error:", e)


def list_user_designs(user_id: str, limit: int = 12):
    """
    Load the signed-in user's own designs.
    The Flask app queries with service role but filters strictly by user_id.
    """
    if not user_id or not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return []

    try:
        response = requests.get(
            f"{SUPABASE_URL}/rest/v1/designs",
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            },
            params={
                "user_id": f"eq.{user_id}",
                "select": "*",
                "order": "created_at.desc",
                "limit": str(limit),
            },
            timeout=30,
        )

        if response.status_code != 200:
            print("Load designs failed:", response.status_code, response.text)
            return []

        return response.json()

    except Exception as e:
        print("Load designs error:", e)
        return []


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


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def assess_photo_quality(image_path: str) -> dict:
    """
    Lightweight local quality check for merchant-uploaded food photos.
    It does not block generation; it gives the owner practical shooting advice.
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            sample = img.convert("RGB")
            sample.thumbnail((640, 640))

            gray = sample.convert("L")
            stats = ImageStat.Stat(sample)
            gray_stats = ImageStat.Stat(gray)
            edge_stats = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES))

            brightness = gray_stats.mean[0]
            contrast = gray_stats.stddev[0]
            sharpness = edge_stats.mean[0]
            min_edge = min(width, height)
            aspect_ratio = width / height if height else 1

            if min_edge >= 1000:
                resolution_score = 100
            elif min_edge >= 750:
                resolution_score = 86
            elif min_edge >= 512:
                resolution_score = 68
            else:
                resolution_score = 45

            brightness_score = clamp(100 - abs(brightness - 140) * 0.85)
            contrast_score = clamp((contrast / 58) * 100)
            sharpness_score = clamp(sharpness * 3.8)

            score = round(
                resolution_score * 0.32
                + brightness_score * 0.24
                + contrast_score * 0.20
                + sharpness_score * 0.24
            )

            suggestions = []
            if min_edge < 750:
                suggestions.append("照片分辨率偏低，建议靠近食物重拍或使用原图上传。")
            if brightness < 85:
                suggestions.append("照片偏暗，建议靠近窗边或用白灯补光。")
            elif brightness > 210:
                suggestions.append("照片偏亮，建议降低曝光，避免白色盘子过曝。")
            if contrast < 34:
                suggestions.append("食物层次不够明显，建议换干净背景并避开强反光。")
            if sharpness < 10:
                suggestions.append("照片可能有点模糊，建议手机对焦后再拍。")
            if aspect_ratio < 0.65 or aspect_ratio > 1.65:
                suggestions.append("画面比例较极端，建议让食物居中并保留四周空间。")

            if score >= 85:
                grade = "Excellent"
                summary = "照片质量很好，可以直接生成商业图。"
            elif score >= 70:
                grade = "Good"
                summary = "照片可用，AI 会进一步增强光线和质感。"
            elif score >= 55:
                grade = "Fair"
                summary = "照片可生成，但重拍会明显提升成品。"
            else:
                grade = "Needs Retake"
                summary = "建议先重拍，成品稳定性会更高。"

            return {
                "score": score,
                "grade": grade,
                "summary": summary,
                "width": width,
                "height": height,
                "brightness": round(brightness, 1),
                "contrast": round(contrast, 1),
                "sharpness": round(sharpness, 1),
                "suggestions": suggestions[:4],
                "channels": {
                    "resolution": round(resolution_score),
                    "brightness": round(brightness_score),
                    "contrast": round(contrast_score),
                    "sharpness": round(sharpness_score),
                },
            }
    except Exception as e:
        return {
            "score": 0,
            "grade": "Unknown",
            "summary": "照片质量检查失败，但仍可尝试生成。",
            "suggestions": [str(e)],
        }


def resolve_visual_types(visual_type: str, platform_pack: str) -> list[str]:
    pack = PLATFORM_PACKS.get((platform_pack or "single").lower(), PLATFORM_PACKS["single"])
    if pack["types"]:
        return pack["types"]

    visual_type = (visual_type or "poster").lower()
    if visual_type not in VISUAL_OUTPUTS:
        visual_type = "poster"
    return [visual_type]


def get_pack_summary(platform_pack: str, visual_types: list[str]) -> dict:
    key = (platform_pack or "single").lower()
    pack = PLATFORM_PACKS.get(key, PLATFORM_PACKS["single"])
    return {
        "key": key if key in PLATFORM_PACKS else "single",
        "label": pack["label"],
        "description": pack["description"],
        "deliverables": [
            {
                "type": item_type,
                "label": VISUAL_OUTPUTS[item_type]["label"],
                "width": VISUAL_OUTPUTS[item_type]["width"],
                "height": VISUAL_OUTPUTS[item_type]["height"],
            }
            for item_type in visual_types
        ],
    }


def build_business_context_note(
    note: str,
    platform_pack: str,
    brand_name: str = "",
    brand_colors: str = "",
    brand_tone: str = "",
) -> str:
    additions = []
    pack = PLATFORM_PACKS.get((platform_pack or "single").lower())
    if pack and platform_pack != "single":
        additions.append(
            f"Target delivery package: {pack['label']}. {pack['description']} "
            "Design for Malaysian delivery and social commerce usage."
        )
    elif (platform_pack or "").lower() == "social_media":
        additions.append(
            "Target delivery package: Social Media Kit. Create assets for Malaysian restaurants "
            "to post on Instagram, Facebook, WhatsApp Status and paid social placements."
        )
    if clean_text(brand_name):
        additions.append(
            f'Brand context: "{clean_text(brand_name)}". Use it as business context only; '
            "do not invent extra brand text unless it appears in the uploaded logo or user-provided title."
        )
    if clean_text(brand_colors):
        additions.append(f"Preferred brand colors: {clean_text(brand_colors)}.")
    if clean_text(brand_tone):
        additions.append(f"Brand mood/style: {clean_text(brand_tone)}.")

    cleaned_note = clean_text(note)
    if additions:
        return "\n".join([cleaned_note, *additions]).strip()
    return cleaned_note


def bundle_download_url(filenames: list[str]) -> str:
    safe_names = [secure_filename(Path(name).name) for name in filenames if name]
    return f"/download-bundle?files={','.join(safe_names)}" if safe_names else ""


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


def truthy_form_value(value: str) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "checked"}


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


def outcome_note_rules(note: str) -> str:
    cleaned = clean_text(note)
    if not cleaned:
        return "No extra user outcome note provided."

    return f"""
USER OUTCOME REQUIREMENT / REMARKS:
{cleaned}

Follow the user outcome requirement as much as possible, but only when it does not conflict with:
- safe area rules
- food identity preservation
- logo clean zone
- text placement rules
- no random text / no fake logo rules
If there is conflict, the fixed safety and preservation rules must be higher priority.
""".strip()


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


def poster_layout_zones(
    hotdeal_safe_zone: bool = False,
    signature_footer_safe_zone: bool = False,
) -> dict[str, str]:
    """Return poster layout zones. Normal mode stays identical; HotDeals mode shifts copy below the app pill."""
    zones = {
        "title": "X 70 to 620, Y 80 to 250",
        "subtitle": "X 70 to 620, Y 255 to 345",
        "logo": "X 800 to 1030, Y 60 to 210",
        "badge": "X 70 to 420, Y 830 to 1010",
        "price": "X 650 to 1010, Y 830 to 1010",
        "food": "X 360 to 980, Y 280 to 860",
    }

    if hotdeal_safe_zone:
        zones.update({
            # Based on the GrabFood mobile card reference: the orange HOTDEALS pill sits
            # across the upper-left/top-middle of a square food image.
            "hotdeal_reservation": "X 0 to 940, Y 0 to 450",
            "hotdeal_pill": "X 70 to 940, Y 55 to 420",
            "title": "X 70 to 600, Y 450 to 580",
            "subtitle": "X 70 to 600, Y 580 to 640",
            "logo": "X 910 to 1060, Y 35 to 180",
            "badge": "X 70 to 420, Y 850 to 960",
            "food": "X 600 to 1010, Y 365 to 790",
        })

    if signature_footer_safe_zone:
        zones.update({
            "signature_footer_reservation": "X 0 to 1080, Y 880 to 1080",
            "badge": "X 70 to 420, Y 690 to 835",
            "price": "X 650 to 1010, Y 690 to 835",
            "food": "X 600 to 1010, Y 365 to 780" if hotdeal_safe_zone else "X 360 to 980, Y 280 to 840",
        })

    return zones


def grabfood_overlay_safe_zone_rules(
    visual_type: str,
    hotdeal_safe_zone: bool = False,
    signature_footer_safe_zone: bool = False,
) -> str:
    """
    Extra GrabFood app overlay safe zones.
    These rules are appended only when the merchant toggles HotDeals or Signature Footer.
    Normal generation remains unchanged.
    """
    if not hotdeal_safe_zone and not signature_footer_safe_zone:
        return ""

    visual_type = (visual_type or "poster").lower()

    if visual_type == "product":
        if hotdeal_safe_zone:
            product_food_area = "X 110 to 630, Y 275 to 555"
        else:
            product_food_area = "X 80 to 640, Y 90 to 580"
        if signature_footer_safe_zone:
            product_food_area = "X 110 to 630, Y 275 to 545" if hotdeal_safe_zone else "X 80 to 640, Y 90 to 570"

        rules = [
            "GRABFOOD OVERLAY SAFE ZONE MODE FOR 1:1 MENU IMAGE:",
            "- These are external app overlay reservation zones, not visible design boxes.",
            "- Do not draw safe zone guides, boxes, rulers, dashed lines, or app UI.",
            "- Do not generate the HOTDEALS button, GrabFood UI, platform badge, safe-zone template, or guide overlay.",
            "- Keep the food accurate and appetizing while leaving reserved overlay space clean.",
        ]
        if hotdeal_safe_zone:
            rules.extend([
                "",
                "HOTDEALS OVERLAY RESERVATION:",
                "- GrabFood mobile cards can place an orange HOTDEALS pill across the upper-left/top-middle of the menu image.",
                "- Reserve X 0 to 615, Y 0 to 260 on the 720x720 product canvas for that future app overlay.",
                "- Treat the likely orange pill footprint as X 45 to 615, Y 35 to 240, with extra padding around it.",
                "- No important food, garnish, steam, container rim, sauce, logo, text, badge, or bright detail inside X 0 to 615, Y 0 to 260.",
                "- Keep the reserved area as simple background / negative space only.",
                "- Place the main food identity mostly below Y 275 and away from the upper-left overlay zone.",
                "- Make the product about 20% smaller than normal HotDeals-off product composition.",
            ])
        if signature_footer_safe_zone:
            rules.extend([
                "",
                "SIGNATURE FOOTER OVERLAY RESERVATION:",
                "- GrabFood Signature-style footer/ribbon can appear near the bottom edge of the menu image.",
                "- Reserve X 0 to 720, Y 595 to 720 on the 720x720 product canvas for the app footer overlay.",
                "- No important food, container edge, garnish, text, logo, steam, or shadow detail inside X 0 to 720, Y 595 to 720.",
                "- Keep the full food product visible mainly inside the adjusted product food area.",
            ])
        rules.extend([
            "",
            "PRODUCT SAFE COMPOSITION OVERRIDE:",
            "- If overlay reservations are active, shrink and lift the food slightly rather than cropping it.",
            f"- Important food details must remain mainly inside {product_food_area}.",
            "- A clean upper-left background is better than a beautiful garnish that will be covered by the app label.",
        ])
        return "\n".join(rules)

    zones = poster_layout_zones(hotdeal_safe_zone, signature_footer_safe_zone)

    rules = [
        "GRABFOOD OVERLAY SAFE ZONE MODE FOR 1:1 POSTER:",
        "- These rules are active only because the merchant selected HotDeals and/or Signature Footer safe zones.",
        "- The normal poster formula still applies, but these overlay reservation rules have higher priority.",
        "- Do not draw safe zone guides, colored boxes, rulers, dashed lines, or app UI in the final image.",
        "- Do not create fake GrabFood logos, fake HOTDEALS buttons, fake platform interface elements, or visible safe-zone templates.",
    ]

    if hotdeal_safe_zone:
        rules.extend([
            "",
            "HOTDEALS OVERLAY RESERVATION:",
            "- The provided GrabFood reference shows the orange HOTDEALS pill over the upper-left/top-middle of the food card.",
            f"- Reserve {zones['hotdeal_reservation']} on the 1080x1080 canvas for that future app overlay.",
            f"- Treat the likely visible pill footprint as {zones['hotdeal_pill']}, with extra padding around it.",
            "- The reserved HotDeals overlay zone must contain only simple background / negative space.",
            f"- No title, subtitle, badge, price, logo, food, plate, bowl, cup, garnish, steam, smoke, bright prop, or important decoration inside {zones['hotdeal_reservation']}.",
            "- Shift the AI-designed main title below the HotDeals reservation.",
            f"- When HotDeals is active, the main title must stay inside {zones['title']}.",
            f"- When HotDeals is active, the subtitle must stay inside {zones['subtitle']}.",
            f"- When HotDeals is active, the restaurant logo clean zone is reduced to the far top-right only: {zones['logo']}.",
            "- Keep the main title in the left-middle of the poster, not the top-left and not the bottom-left.",
            "- The subtitle must sit directly below the main title, with clear spacing and no overlap.",
            "- No title letters, title shadows, subtitle letters, or decorative title strokes may appear above Y 440 or below Y 650.",
            f"- Reserve the lower-left badge area {zones['badge']} for the user badge if provided.",
            "- Do not place food, title, subtitle, steam, or decoration inside the lower-left badge area.",
            "- Important food details should stay on the right side and not touch the title, subtitle, or badge area.",
            "- Make the hero food roughly 20% smaller than the normal poster composition so the left-middle title and lower-left badge have clear breathing room.",
        ])

    if signature_footer_safe_zone:
        rules.extend([
            "",
            "SIGNATURE FOOTER OVERLAY RESERVATION:",
            "- GrabFood Signature-style footer/ribbon can appear at the bottom of a food card, often bottom-right or across the lower edge.",
            f"- Reserve {zones['signature_footer_reservation']} on the 1080x1080 canvas for that app footer overlay.",
            "- The reserved Signature Footer zone must contain only simple background / negative space.",
            f"- No title, subtitle, badge, price, logo, food, plate, bowl, cup, garnish, steam, smoke, or important decoration inside {zones['signature_footer_reservation']}.",
            "- Keep important food details above Y 860.",
            f"- If a user badge is provided, place it inside {zones['badge']}.",
            f"- If a price is provided, place it inside {zones['price']}.",
            "- Badge and price must not overlap the future footer reservation.",
        ])

    rules.extend([
        "",
        "COMBINED OVERLAY SAFETY:",
        "- All custom GPT Image 2 typography is still encouraged: bold, premium, hand-lettered, modern Chinese or editorial food-ad typography.",
        "- Creative typography must fit inside the adjusted safe areas and must not enter any overlay reservation zone.",
        "- If the title, badge, or price is long, reduce size or use tighter layout instead of entering the overlay reservation zones.",
        "- Food must remain recognizable and appetizing, but it must not sit under the HotDeals or Signature Footer overlay reservations.",
        f"- Keep the hero food mainly inside {zones['food']} when overlay reservations are active.",
        "- If HotDeals is active, prioritize a readable left-middle title and clean lower-left badge area over making the food large; the upper-left and upper-middle canvas should stay quiet.",
        "- The final artwork should not show the reserved app overlays; it should simply compose around where the delivery app will place them.",
    ])
    return "\n".join(rules)


def poster_absolute_negative_rules(
    hotdeal_safe_zone: bool = False,
    signature_footer_safe_zone: bool = False,
) -> str:
    zones = poster_layout_zones(hotdeal_safe_zone, signature_footer_safe_zone)

    rules = [
        "ABSOLUTE NEGATIVE RULES:",
        f"- No title outside {zones['title']}.",
        f"- No subtitle outside {zones['subtitle']}.",
        f"- No badge outside {zones['badge']}.",
        f"- No price outside {zones['price']}.",
        f"- No food, text, steam, smoke or decoration in logo clean zone {zones['logo']}.",
    ]

    if hotdeal_safe_zone:
        rules.append(f"- No food, text, badge, price, logo, steam, smoke or decoration in HotDeals overlay reservation {zones['hotdeal_reservation']}.")
    if signature_footer_safe_zone:
        rules.append(f"- No food, text, badge, price, logo, steam, smoke or decoration in Signature Footer overlay reservation {zones['signature_footer_reservation']}.")

    rules.extend([
        "- No safe area guide lines.",
        "- No visible boxes showing safe area.",
        "- No rulers.",
        "- No dashed lines.",
        "- No template guides.",
    ])
    return "\n".join(rules)


# ======================================================
# GPT IMAGE PROMPTS
# ======================================================

def build_banner_prompt(title: str, subtitle: str, badge: str, price: str, style: str, note: str = "") -> str:
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
- Main title must never exceed 2 lines.
- Do not split the main title into 3 lines.
- If title is long, reduce font size first.
- If still too long, use tighter letter spacing.
- If still too long, make each line wider but keep inside X 60 to 500.
- Long title may wrap into maximum 2 lines only.
- Never push subtitle, badge, or price downward because of a long title.
- Subtitle must be inside X 60 to 500 and Y 320 to 390, only if subtitle is provided.
- Badge must be inside X 60 to 270 and Y 430 to 520, only if badge is provided.
- Price must be inside X 300 to 520 and Y 430 to 520, only if price is provided.
- Badge and price must not overlap each other.
- Badge and price must not overlap the food.
- Badge and price must not go below Y 520.

TITLE WRAPPING RULE:
- Main title must never exceed 2 lines.
- A 3-line title is forbidden.
- If the title is long, make the title smaller instead of adding a third line.
- Keep the title inside X 60 to 500 and Y 180 to 320.
- The title must not push subtitle, badge, or price downward.
- The title must not overlap subtitle, badge, price, food, or logo safe zone.
- Use smart line breaking so the title looks balanced in 2 lines maximum.

BADGE SAFETY RULE:
- Badge must stay inside X 60 to 270 and Y 430 to 520.
- Badge must never go outside the safe area.
- Badge must never be below Y 520.
- If title is long, do not move badge downward.
- If badge text is long, reduce badge size and font size.
- Badge must not overlap price.
- Badge must not overlap food.
- Badge must remain fully readable.

PRICE SAFETY RULE:
- Price must stay inside X 300 to 520 and Y 430 to 520.
- Price must never go outside the safe area.
- Price must never be below Y 520.
- If title is long, do not move price downward.
- If price text is long, reduce price font size and price element size.
- Price must not overlap badge.
- Price must not overlap food.
- Price must remain fully readable.

TEXT FITTING RULE:
- Automatically resize typography to fit the safe area.
- Readability and staying inside safe area are more important than large text.
- Never allow title overflow.
- Never allow subtitle overflow.
- Never allow badge overflow.
- Never allow price overflow.
- Never place any text outside X 60 to 520 and Y 150 to 560.
- If a title is too long, make it smaller or use up to 2 lines only.
- If badge or price is too long, make it smaller and keep it inside the assigned box.
- Do not move lower elements down to solve title overflow.

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
- No 3-line main title.
- No title outside X 60 to 500, Y 180 to 320.
- No text above Y 150.
- No text below Y 560.
- No text outside X 60 to 520.
- No badge outside X 60 to 270, Y 430 to 520.
- No badge below Y 520.
- No price outside X 300 to 520, Y 430 to 520.
- No price below Y 520.
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

{outcome_note_rules(note)}
"""


def build_poster_prompt(
    title: str,
    subtitle: str,
    badge: str,
    price: str,
    style: str,
    note: str = "",
    hotdeal_safe_zone: bool = False,
    signature_footer_safe_zone: bool = False,
) -> str:
    zones = poster_layout_zones(hotdeal_safe_zone, signature_footer_safe_zone)
    hotdeal_food_scale_rule = (
        "- HOTDEALS MODE: make the food hero about 20% smaller than normal, keep it compact on the right side, and leave clear space for the left-middle title plus the lower-left badge area."
        if hotdeal_safe_zone
        else ""
    )
    hotdeal_title_floor_rule = (
        "- HOTDEALS MODE: place the main title in the left-middle of the poster, inside X 70 to 600 and Y 450 to 580. Put the subtitle directly below it inside X 70 to 600 and Y 580 to 640. No title/subtitle/shadow/decoration above Y 440 or below Y 650. Keep the lower-left badge area X 70 to 420 and Y 850 to 960 clean for the badge."
        if hotdeal_safe_zone
        else ""
    )

    return f"""
Analyze the uploaded food image carefully.

Your task is to create a premium square food advertisement poster.

FINAL OUTPUT:
- 1:1 square poster.
- Final canvas must be 1080px × 1080px.
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
- not entering the logo clean zone

If the uploaded item is cold food, dessert, or drink, do not add hot steam unless naturally suitable.

CRITICAL POSTER CANVAS MAP:
- Full poster canvas: 1080 wide × 1080 high.
- Main title safe area: {zones['title']}.
- Subtitle safe area: {zones['subtitle']}.
- Logo clean zone: {zones['logo']}.
- Badge safe area: {zones['badge']}.
- Price safe area: {zones['price']}.
- Food hero area: {zones['food']}.

FIXED POSTER LAYOUT:
TITLE AREA:
- Main title must be in the assigned title area.
- Main title must stay inside {zones['title']}.
- Main title must not cover the food.
- If title is long, wrap it into maximum 2 lines and reduce font size automatically.
{hotdeal_title_floor_rule}

SUBTITLE:
- Subtitle must be directly below the main title only if provided.
- Subtitle must stay inside {zones['subtitle']}.
- Subtitle must not cover the food.
- If subtitle is empty, do not create subtitle or any extra tagline.

TOP RIGHT LOGO SAFE AREA:
- Logo will be overlaid later by code.
- Keep {zones['logo']} completely clean.
- This zone must contain only simple background / negative space.
- No food.
- No text.
- No decorations.
- No smoke.
- No steam.
- No garnish.
- No bright object.
- No fake logo.

FOOD HERO:
- Food should be the hero visual.
- Food should be placed mainly inside {zones['food']}.
- Food may extend slightly if visually natural, but must not cover title, subtitle, logo, badge, or price.
{hotdeal_food_scale_rule}
- Keep the full plate, bowl, box, cup, or important food parts visible.
- Do not crop the main product.
- Do not place important food under the title area.
- Do not place important food under the logo clean zone.

BOTTOM LEFT BADGE:
- Badge must be at the bottom-left only if provided.
- Badge must stay inside {zones['badge']}.
- Badge must not cover food.
- Badge must not overlap price.
- If badge is empty, do not create badge, sticker, ribbon, label, or placeholder.

BOTTOM RIGHT PRICE:
- Price must be at the bottom-right only if provided.
- Price must stay inside {zones['price']}.
- Price must not cover food.
- Price must not overlap badge.
- If price is empty, do not create price, currency, discount, number, price box, or placeholder.

TEXT FITTING RULE:
- Automatically resize typography to fit inside the assigned safe areas.
- Readability and staying inside safe area are more important than large text.
- Never allow title overflow.
- Never allow subtitle overflow.
- Never allow badge overflow.
- Never allow price overflow.
- Never crop text at the canvas edges.
- Do not place any user text outside its assigned safe area.

POSTER DESIGN:
Create a premium square advertising poster design with professional art direction.
The layout should feel modern, authentic, appetizing and high-converting.
The poster should look like a professional food brand campaign, not a template.
Do not show safe area guides, rulers, dashed lines, colored boxes, or layout annotations.

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

{grabfood_overlay_safe_zone_rules("poster", hotdeal_safe_zone, signature_footer_safe_zone)}

{poster_absolute_negative_rules(hotdeal_safe_zone, signature_footer_safe_zone)}

STYLE OPTION:
{normalize_style(style)}

USER TEXT:
{optional_text_rules(title, subtitle, badge, price)}

{outcome_note_rules(note)}
"""


def build_product_prompt(
    style: str,
    title: str = "",
    note: str = "",
    has_side: bool = False,
    has_drink: bool = False,
    hotdeal_safe_zone: bool = False,
    signature_footer_safe_zone: bool = False,
) -> str:
    side_rule = "A side/snack image is provided. Use the uploaded side/snack as a real supporting item. Place it behind the main dish, slightly to one side, smaller than the main dish." if has_side else "No side/snack image is provided. Do not invent any side/snack."
    drink_rule = "A drink image is provided. Use the uploaded drink as a real supporting item. Place it behind the main dish, slightly to one side, smaller than the main dish." if has_drink else "No drink image is provided. Do not invent any drink."
    product_tag = clean_text(title)
    product_tag_output_rule = (
        f'- One designed product recommendation label is allowed because the user provided a product title tag: "{product_tag}".'
        if product_tag
        else "- No text, no logo, no price, no badge, no watermark, no border."
    )
    product_tag_rules = f"""
OPTIONAL PRODUCT TAG:
- The user provided this exact product tag text: "{product_tag}".
- Create exactly one premium recommendation label in the top-left area.
- User's requested large design area is X 0 to 940, Y 0 to 450 on a 1080-style square canvas.
- Because the final product canvas is 720x720, use the equivalent large label design area X 0 to 627, Y 0 to 300.
- The visible label should sit mainly inside X 24 to 560, Y 28 to 210 on the final 720x720 product canvas.
- The tag can be larger than a sticker and should feel intentionally designed, but it must not become a full poster headline.
- The tag must be a vivid food-promo label, preferably orange, orange-red, tomato red, or warm red.
- Use a bright solid or subtly shaded label base with tasteful depth, soft drop shadow, and premium restaurant-menu styling.
- White, warm-white, or cream lettering is preferred for contrast; add subtle stroke/shadow if needed for readability.
- You may add a small highlight, ribbon notch, brush edge, or layered label backing, but keep it clean and commercial.
- Use GPT Image 2's creative typography: custom display lettering, tasteful hierarchy, subtle stroke/shadow, and polished spacing.
- The label should be visually energetic and appetizing while the overall product background remains pure white.
- Keep the main product fully visible. If needed, make the food about 8% to 12% smaller or shift it slightly lower/right so the designed label does not cover the product.
- Use only the exact user-provided tag text. Do not invent extra words, discount text, platform names, fake logos, or unrelated badges.
- Do not create any other text anywhere else in the product image.
""" if product_tag else """
OPTIONAL PRODUCT TAG:
- No product tag text was provided.
- Do not create any label, sticker, tag, badge, title, subtitle, price, or other text.
"""
    strict_text_rules = (
        f'- No text except the single exact top-left product tag: "{product_tag}".\n- No random words.\n- No logo.\n- No price.\n- No extra badge or sticker beyond that one white tag.'
        if product_tag
        else "- No text.\n- No random words.\n- No logo.\n- No price.\n- No badge."
    )
    product_composition_tag_rule = (
        "- Because a larger top-left recommendation label is active, compose the food slightly lower/right and about 8% to 12% smaller if needed, while keeping the white background clean."
        if product_tag
        else ""
    )

    return f"""
Analyze the uploaded food image carefully before generating.

Your task is to create a REALISTIC clean food product photo for menu listing, not a fantasy advertising render.

FINAL OUTPUT:
- 1:1 square product image.
- Final file will be resized to 720px × 720px for faster generation and lighter downloads.
- Suitable for Foodpanda menu, GrabFood menu, restaurant menu, ecommerce listing, POS system and delivery platforms.
{product_tag_output_rule}

IMAGE RESTORATION / BLUR RECOVERY:
- The uploaded image may be low resolution, blurry, compressed, dark, noisy, or taken from WhatsApp / screenshots.
- First restore the product naturally: improve sharpness, lighting, texture, color accuracy and food detail.
- Recover realistic food texture where possible, but do not hallucinate a different dish.
- If the image is slightly blurry, make it look like a clean professional food photo.
- If the image is very blurry, preserve only clearly visible food identity and avoid guessing unknown ingredients.
- Do not invent ingredients to compensate for blur.

45-DEGREE CAMERA ANGLE STANDARD:
- Always convert the main food into a professional 45-degree camera angle product shot.
- The camera should be slightly above and in front of the food, like realistic menu product photography.
- If the uploaded photo is top-down / flat lay / overhead, reconstruct it into a believable 45-degree front perspective.
- Never output a pure top-down flat lay product image.
- Never output an extreme side view.
- Keep the plate, bowl, lunch box, cup, or container shape realistic in 45-degree perspective.

WHITE BACKGROUND / SOFT SHADOW:
- Use a pure white seamless studio background.
- Keep the background clean, bright and uncluttered.
- Add only a subtle natural soft contact shadow underneath the product.
- Shadow must be gentle, realistic and barely visible, not dramatic.
- Do not use restaurant scenes, table surfaces, props, colored backgrounds, gradients, tiles, wood, smoke-filled backgrounds, or decorative objects.

FOOD IDENTITY PRESERVATION:
- The generated food must still look like the same real dish uploaded by the user.
- Do not change the dish type.
- Do not change the meat type.
- Do not change rice/noodle/base type.
- Do not replace sauce, toppings, vegetables, garnish, container, bowl, plate or packaging unless cleanup is necessary.
- Do not make the product look more expensive by turning it into a different dish.
- Improve cleanliness, lighting, sharpness and plating only while preserving the original product identity.

REALISTIC FOOD PHOTOGRAPHY / ANTI-AI LOOK:
- The result must look like a real food product photographed in a small professional studio.
- Prioritize realism over beauty.
- Use natural lens perspective and believable shadows.
- Avoid CGI, 3D render, illustration, plastic texture, fake glossy surfaces, overly perfect food, surreal details, melted shapes, duplicated ingredients or AI-looking symmetry.
- Avoid exaggerated steam, fake smoke, fantasy lighting, fake bokeh, overly saturated color and impossible food geometry.
- Do not create a stock-photo-looking dish that no longer matches the upload.
- Make edges clean but not cut-out artificial.
- The food should look like a real product that can be served by the restaurant.

BUNDLE PRODUCT RULES:
- The first uploaded image is always the main dish and must be the hero product in front.
- Main dish must stay largest, closest to camera, and visually dominant.
- {side_rule}
- {drink_rule}
- If both side/snack and drink are provided, place both behind the main dish, balanced left/right, with the main dish clearly in front.
- Side and drink must be smaller than the main dish and must not block the main dish.
- Do not replace the main dish with the side or drink.
- Do not invent extra bundle items that were not uploaded.
- Bundle must still be on pure white background with subtle contact shadows.

PRODUCT COMPOSITION:
- Center the product or bundle.
- Main product should occupy about 62% to 74% of the 720×720 canvas.
- Bundle can occupy about 68% to 80% of the canvas.
- Leave clean white breathing space around the product.
{product_composition_tag_rule}
- Keep the full plate, bowl, box, cup, container and important food parts visible.
- Do not crop important parts.
- Do not make the food touch the canvas edges.

{product_tag_rules}

{grabfood_overlay_safe_zone_rules("product", hotdeal_safe_zone, signature_footer_safe_zone)}

HOT FOOD EFFECT:
- If the main dish is hot food, add only extremely subtle natural steam if it improves realism.
- Steam must be light, elegant and barely visible.
- Do not use heavy smoke.
- Do not let steam make the image look AI-generated.
- If the item is cold food, dessert, drink, packaged product, or not clearly hot, do not add steam.

STRICT NEGATIVE:
{strict_text_rules}
- No hands.
- No people.
- No table scene.
- No restaurant scene.
- No colored background.
- No props.
- No unrelated ingredients.
- No extra side or drink unless uploaded.
- No AI fantasy style.
- No 3D render.
- No illustration.
- No cartoon look.
- No fake packaging label.

STYLE OPTION:
{normalize_style(style)}

{outcome_note_rules(note)}
"""



def normalize_campaign_goal(goal: str) -> str:
    value = (goal or "best_seller").lower().strip()
    mapping = {
        "new_product": "New product launch: introduce the dish clearly and make it feel fresh, new, and worth trying.",
        "best_seller": "Best seller campaign: make the dish look popular, trusted, and highly craveable.",
        "promotion": "Promotion campaign: emphasize value, urgency, and conversion without inventing discounts unless the user provided them.",
        "combo": "Combo meal campaign: present the main dish as a complete meal set when side or drink images are provided.",
        "festival": "Festival campaign: create a warm seasonal food promotion mood without adding fake festival text unless provided.",
        "branding": "Restaurant branding campaign: focus on premium brand impression, food quality, and memorable visual identity.",
    }
    return mapping.get(value, mapping["best_seller"])


def build_social_prompt(format_key: str, title: str, subtitle: str, badge: str, price: str, style: str, note: str, campaign_goal: str, has_side: bool = False, has_drink: bool = False) -> str:
    spec = SOCIAL_OUTPUTS.get(format_key, SOCIAL_OUTPUTS["feed"])
    label = spec["label"]
    w = spec["width"]
    h = spec["height"]

    if format_key == "story":
        layout_rules = """
STORY / STATUS LAYOUT RULES:
- Design for 9:16 vertical social media viewing.
- Keep the most important food hero in the middle area.
- Leave clean space at the top for brand/logo impression.
- Place title and key message in a large readable hierarchy.
- Place badge/price/CTA style element near the lower third only if user provided badge or price.
- Keep all important content away from the extreme top and bottom app UI zones.
- The design should look premium on Instagram Story, Facebook Story and WhatsApp Status.
"""
    elif format_key == "portrait":
        layout_rules = """
PORTRAIT POST LAYOUT RULES:
- Design for 4:5 Instagram portrait feed.
- Strong hero food composition with high conversion value.
- Food should occupy around 45% to 60% of the canvas.
- Typography must be readable on mobile.
- Keep a premium editorial food campaign look.
"""
    elif format_key == "facebook_ad":
        layout_rules = """
FACEBOOK AD LAYOUT RULES:
- Design for a horizontal Facebook ad / campaign visual.
- Strong left-right hierarchy: clear message area and appetizing food hero area.
- Make it conversion-focused, clean and clickable.
- Avoid clutter and keep text highly readable.
"""
    else:
        layout_rules = """
FEED POST LAYOUT RULES:
- Design for 1:1 Instagram / Facebook feed.
- Balanced square campaign layout.
- Food should be the hero and occupy around 45% to 55% of the image.
- Typography must be readable in mobile feed.
"""

    bundle_rules = """
BUNDLE COMPOSITION:
- If side image is uploaded, include the side/snack behind or slightly beside the main dish.
- If drink image is uploaded, include the drink behind the main dish.
- If both side and drink are uploaded, main dish must stay in front; side and drink appear behind the main dish as a bundle set.
- Do not let side or drink overpower the main dish.
""" if (has_side or has_drink) else "Do not add side dishes or drinks unless they appear in the uploaded image."

    return f"""
Analyze the uploaded food image carefully and create a professional restaurant social media campaign visual.

FINAL OUTPUT:
- Format: {label}
- Final canvas: {w}px × {h}px.
- Suitable for restaurant marketing, Instagram, Facebook, WhatsApp Status, food delivery promotion and social media posting.
- No watermark.
- No border.
- No fake platform UI.
- No random text.
- No misspelled text.
- Do not invent promotion words, discounts, brand names or slogans.

CAMPAIGN GOAL:
{normalize_campaign_goal(campaign_goal)}

FOOD IDENTITY PRESERVATION:
- Preserve the uploaded food identity.
- The generated food must look like the same real dish from the uploaded photo.
- Do not change pork into chicken, rice into noodles, or one cuisine into another cuisine.
- Do not replace key ingredients.
- Do not redesign the dish into a different dish.
- Improve lighting, texture, color and styling while keeping the real food recognizable.

IMAGE RESTORATION / BLUR RECOVERY:
- The uploaded food may be slightly blurry, compressed, low resolution or taken from a phone.
- Restore natural sharpness and food texture before creating the campaign visual.
- Improve clarity, lighting and color accuracy.
- Do not invent missing ingredients when the image is unclear.

REALISTIC FOOD PHOTOGRAPHY:
- Make the final result look like a real professional food campaign photo, not AI generated.
- Use realistic commercial food photography lighting.
- Avoid CGI, illustration, plastic-looking food, over-smooth texture, fake reflections and fantasy styling.
- Keep natural shadows and believable depth.
- Food must look appetizing, fresh and edible.

SOCIAL MEDIA ART DIRECTION:
- Premium restaurant campaign design.
- Strong mobile-first composition.
- Clear visual hierarchy.
- Modern professional typography.
- Attractive but not overcrowded.
- The image should feel designed by a professional food marketing designer.

{layout_rules}

BUNDLE / EXTRA ITEMS:
{bundle_rules}

TYPOGRAPHY REQUIREMENTS:
- Generate typography directly inside the artwork.
- Use only exact user-provided text.
- Do not invent extra words.
- Keep Chinese text clean, premium and readable.
- Keep English text professional and campaign-ready.
- Text must not be distorted, misspelled, duplicated or randomly generated.
- If no text is provided for a field, do not create placeholder text.

USER TEXT:
{optional_text_rules(title, subtitle, badge, price)}

STYLE OPTION:
{normalize_style(style)}

USER OUTCOME REQUIREMENT:
{clean_text(note) if clean_text(note) else "No extra outcome requirement provided."}

IMPORTANT PRIORITY:
- Follow the outcome requirement only if it does not conflict with food identity preservation, readability, realism and platform-safe layout.
- Realistic food photography and correct dish identity are higher priority than creative styling.
"""


def generate_social_visual(
    image_path: str,
    logo_path: str,
    format_key: str,
    title: str,
    subtitle: str,
    badge: str,
    price: str,
    style: str,
    note: str,
    campaign_goal: str,
    side_path: str = "",
    drink_path: str = "",
) -> str:
    format_key = (format_key or "feed").lower()
    spec = SOCIAL_OUTPUTS.get(format_key, SOCIAL_OUTPUTS["feed"])
    prompt = build_social_prompt(
        format_key=format_key,
        title=title,
        subtitle=subtitle,
        badge=badge,
        price=price,
        style=style,
        note=note,
        campaign_goal=campaign_goal,
        has_side=bool(side_path),
        has_drink=bool(drink_path),
    )

    image_bytes = call_openai_image_edit([image_path, side_path, drink_path], prompt, spec["openai_size"])

    filename = f"{int(time.time() * 1000)}_social_{format_key}_{spec['width']}x{spec['height']}.png"
    output_path = OUTPUT_FOLDER / filename

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    if spec.get("resize") == "cover":
        resize_cover(str(output_path), spec["width"], spec["height"])
    else:
        resize_exact(str(output_path), spec["width"], spec["height"])

    if logo_path:
        overlay_logo(str(output_path), logo_path, "poster")

    return filename


# ======================================================
# IMAGE GENERATION
# ======================================================

def call_openai_image_edit(image_paths, prompt: str, size: str) -> bytes:
    if isinstance(image_paths, (str, Path)):
        image_paths = [str(image_paths)]

    opened_files = []
    try:
        for image_path in image_paths:
            if image_path and os.path.exists(str(image_path)):
                opened_files.append(open(image_path, "rb"))

        if not opened_files:
            raise ValueError("No valid image files provided for generation.")

        result = get_openai_client().images.edit(
            model=IMAGE_MODEL,
            image=opened_files,
            prompt=prompt,
            size=size,
        )

        return base64.b64decode(result.data[0].b64_json)
    finally:
        for f in opened_files:
            try:
                f.close()
            except Exception:
                pass


def generate_visual(
    image_path: str,
    logo_path: str,
    visual_type: str,
    title: str,
    subtitle: str,
    badge: str,
    price: str,
    style: str,
    note: str = "",
    side_path: str = "",
    drink_path: str = "",
    hotdeal_safe_zone: bool = False,
    signature_footer_safe_zone: bool = False,
) -> str:
    visual_type = (visual_type or "poster").lower()

    if visual_type == "banner":
        prompt = build_banner_prompt(title, subtitle, badge, price, style, note)
        openai_size = "1536x1024"
        suffix = "banner_1080x600"
        target_w, target_h = BANNER_W, BANNER_H
    elif visual_type == "product":
        prompt = build_product_prompt(
            style,
            title=title,
            note=note,
            has_side=bool(side_path),
            has_drink=bool(drink_path),
            hotdeal_safe_zone=hotdeal_safe_zone,
            signature_footer_safe_zone=signature_footer_safe_zone,
        )
        openai_size = "1024x1024"
        suffix = "product_720x720"
        target_w, target_h = PRODUCT_W, PRODUCT_H
    else:
        prompt = build_poster_prompt(
            title,
            subtitle,
            badge,
            price,
            style,
            note,
            hotdeal_safe_zone=hotdeal_safe_zone,
            signature_footer_safe_zone=signature_footer_safe_zone,
        )
        openai_size = "1024x1024"
        suffix = "poster_1080x1080"
        target_w, target_h = POSTER_W, POSTER_H

    image_bytes = call_openai_image_edit([image_path, side_path, drink_path] if visual_type == "product" else image_path, prompt, openai_size)

    filename = f"{int(time.time() * 1000)}_{suffix}.png"
    output_path = OUTPUT_FOLDER / filename

    with open(output_path, "wb") as f:
        f.write(image_bytes)

    if visual_type == "banner":
        resize_cover(str(output_path), target_w, target_h)
    else:
        resize_exact(str(output_path), target_w, target_h)

    if visual_type in {"poster", "banner"}:
        overlay_logo(str(output_path), logo_path, visual_type, hotdeal_safe_zone=hotdeal_safe_zone)

    return filename


# ======================================================
# ROUTES
# ======================================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/social-media-kit")
def social_media_kit_page():
    return render_template("social_media_kit.html")


@app.route("/generate", methods=["POST"])
def generate():
    try:
        visual_type = request.form.get("type", "poster")
        platform_pack = request.form.get("platform_pack", "single").strip().lower()
        title = request.form.get("title", "").strip()
        subtitle = request.form.get("subtitle", "").strip()
        badge = request.form.get("badge", "").strip()
        price = request.form.get("price", "").strip()
        style = request.form.get("style", "AI Auto Detect").strip()
        note = request.form.get("note", "").strip()
        brand_name = request.form.get("brand_name", "").strip()
        brand_colors = request.form.get("brand_colors", "").strip()
        brand_tone = request.form.get("brand_tone", "").strip()
        hotdeal_safe_zone = truthy_form_value(request.form.get("hotdeal_safe_zone", ""))
        signature_footer_safe_zone = truthy_form_value(request.form.get("signature_footer_safe_zone", ""))
        visual_types = resolve_visual_types(visual_type, platform_pack)
        pack_summary = get_pack_summary(platform_pack, visual_types)
        generation_note = build_business_context_note(
            note=note,
            platform_pack=platform_pack,
            brand_name=brand_name,
            brand_colors=brand_colors,
            brand_tone=brand_tone,
        )

        # User info comes from static/app.js after login.
        user_id = request.form.get("user_id", "").strip()
        user_email = request.form.get("user_email", "").strip()

        allowed, profile, limit_reason = check_generation_limit(user_id, user_email)

        if not allowed:
            if limit_reason == "trial_expired":
                error_message = "Your 2-day free trial has expired. Upgrade to Pro to continue generating images."
            elif limit_reason == "trial_exhausted":
                error_message = "You have used all 10 free trial images. Upgrade to Pro to generate more images."
            else:
                error_message = "Your trial limit has been reached. Upgrade to Pro to continue."

            return jsonify({
                "success": False,
                "error": error_message,
                "limit_reached": True,
                "limit_reason": limit_reason,
                "profile": profile,
            }), 403

        food_images = [f for f in request.files.getlist("food_image") if f and f.filename]
        logo_file = request.files.get("logo")
        side_file = request.files.get("side_image")
        drink_file = request.files.get("drink_image")

        if not food_images:
            return jsonify({"success": False, "error": "Please upload food image."}), 400

        # Platform packs are dish-level kits. Product-only mode supports batch upload.
        if platform_pack != "single" or visual_type.lower() != "product":
            food_images = food_images[:1]

        required_generations = len(food_images) * len(visual_types)

        # Prevent a trial user from bypassing the limit with batch upload or platform kits.
        if profile and (profile.get("plan") or "trial").lower() != "pro":
            trial_limit = int(profile.get("trial_limit") or 10)
            trial_used = int(profile.get("trial_used") or 0)
            remaining = max(0, trial_limit - trial_used)
            if required_generations > remaining:
                return jsonify({
                    "success": False,
                    "error": f"Your trial has {remaining} generation(s) remaining. This request needs {required_generations}. Please reduce outputs or upgrade to Pro.",
                    "limit_reached": True,
                    "limit_reason": "trial_batch_exceeds_remaining",
                    "profile": profile,
                }), 403

        logo_path = ""
        if logo_file and logo_file.filename:
            logo_path = save_upload(logo_file, LOGO_FOLDER)

        side_path = ""
        if side_file and side_file.filename:
            side_path = save_upload(side_file, UPLOAD_FOLDER)

        drink_path = ""
        if drink_file and drink_file.filename:
            drink_path = save_upload(drink_file, UPLOAD_FOLDER)

        safe_user_folder = secure_filename(user_id) if user_id else "public"
        generated_items = []
        quality_reports = []

        for idx, food_image in enumerate(food_images, start=1):
            image_path = save_upload(food_image, UPLOAD_FOLDER)
            quality_report = assess_photo_quality(image_path)
            quality_report["source_filename"] = Path(image_path).name
            quality_report["batch_index"] = idx
            quality_reports.append(quality_report)

            for item_type in visual_types:
                filename = generate_visual(
                    image_path=image_path,
                    logo_path=logo_path,
                    visual_type=item_type,
                    title=title,
                    subtitle=subtitle,
                    badge=badge,
                    price=price,
                    style=style,
                    note=generation_note,
                    side_path=side_path,
                    drink_path=drink_path,
                    hotdeal_safe_zone=hotdeal_safe_zone,
                    signature_footer_safe_zone=signature_footer_safe_zone,
                )

                local_output_path = OUTPUT_FOLDER / filename
                local_image_url = output_url(filename)
                local_download_url = f"/download/{filename}"
                storage_key = f"{safe_user_folder}/{filename}"
                storage_url = upload_to_supabase_storage(str(local_output_path), storage_key)

                image_url = storage_url or local_image_url
                download_url = storage_url or local_download_url
                item_meta = VISUAL_OUTPUTS[item_type]

                item_title = title or ("Product Bundle" if (side_path or drink_path) else item_meta["label"])
                if len(food_images) > 1:
                    item_title = f"{item_title} #{idx}"
                if len(visual_types) > 1:
                    item_title = f"{item_title} - {item_meta['label']}"

                save_design_to_supabase(
                    user_id=user_id,
                    user_email=user_email,
                    image_url=image_url,
                    download_url=download_url,
                    visual_type=item_type,
                    title=item_title,
                )

                increment_usage(user_id)

                generated_items.append({
                    "type": item_type,
                    "label": item_meta["label"],
                    "width": item_meta["width"],
                    "height": item_meta["height"],
                    "filename": filename,
                    "image_url": image_url,
                    "download_url": download_url,
                    "storage_uploaded": bool(storage_url),
                    "quality_score": quality_report.get("score"),
                })

        updated_profile = get_or_create_profile(user_id, user_email)
        first_item = generated_items[0]
        local_filenames = [item["filename"] for item in generated_items]

        return jsonify({
            "success": True,
            "filename": first_item["filename"],
            "image_url": first_item["image_url"],
            "download_url": first_item["download_url"],
            "bundle_download_url": bundle_download_url(local_filenames),
            "items": generated_items,
            "batch_count": len(generated_items),
            "requested_generations": required_generations,
            "platform_pack": pack_summary,
            "safe_zones": {
                "hotdeal": hotdeal_safe_zone,
                "signature_footer": signature_footer_safe_zone,
            },
            "quality_reports": quality_reports,
            "recent": list_recent_outputs(6),
            "storage_uploaded": first_item["storage_uploaded"],
            "profile": updated_profile,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/generate-social-kit", methods=["POST"])
def generate_social_kit():
    try:
        title = request.form.get("title", "").strip()
        subtitle = request.form.get("subtitle", "").strip()
        badge = request.form.get("badge", "").strip()
        price = request.form.get("price", "").strip()
        style = request.form.get("style", "AI Auto Detect").strip()
        note = request.form.get("note", "").strip()
        campaign_goal = request.form.get("campaign_goal", "best_seller").strip()
        brand_name = request.form.get("brand_name", "").strip()
        brand_colors = request.form.get("brand_colors", "").strip()
        brand_tone = request.form.get("brand_tone", "").strip()
        generation_note = build_business_context_note(
            note=note,
            platform_pack="social_media",
            brand_name=brand_name,
            brand_colors=brand_colors,
            brand_tone=brand_tone,
        )

        user_id = request.form.get("user_id", "").strip()
        user_email = request.form.get("user_email", "").strip()

        outputs = request.form.getlist("outputs")
        outputs = [o for o in outputs if o in SOCIAL_OUTPUTS]
        if not outputs:
            outputs = ["feed"]

        allowed, profile, limit_reason = check_generation_limit(user_id, user_email)
        if not allowed:
            if limit_reason == "trial_expired":
                error_message = "Your 2-day free trial has expired. Upgrade to Pro to continue generating images."
            elif limit_reason == "trial_exhausted":
                error_message = "You have used all 10 free trial images. Upgrade to Pro to generate more images."
            else:
                error_message = "Your trial limit has been reached. Upgrade to Pro to continue."
            return jsonify({"success": False, "error": error_message, "limit_reached": True, "limit_reason": limit_reason, "profile": profile}), 403

        # Prevent trial users from generating more selected outputs than remaining credits.
        if profile and (profile.get("plan") or "trial").lower() != "pro":
            trial_limit = int(profile.get("trial_limit") or 10)
            trial_used = int(profile.get("trial_used") or 0)
            remaining = max(0, trial_limit - trial_used)
            if len(outputs) > remaining:
                return jsonify({
                    "success": False,
                    "error": f"Your trial has {remaining} generation(s) remaining. Please select {remaining} output(s) or upgrade to Pro.",
                    "limit_reached": True,
                    "limit_reason": "trial_social_outputs_exceed_remaining",
                    "profile": profile,
                }), 403

        food_file = request.files.get("food_image")
        logo_file = request.files.get("logo")
        side_file = request.files.get("side_image")
        drink_file = request.files.get("drink_image")

        if not food_file or not food_file.filename:
            return jsonify({"success": False, "error": "Please upload main food image."}), 400

        image_path = save_upload(food_file, UPLOAD_FOLDER)
        quality_report = assess_photo_quality(image_path)
        quality_report["source_filename"] = Path(image_path).name
        quality_report["batch_index"] = 1

        logo_path = ""
        if logo_file and logo_file.filename:
            logo_path = save_upload(logo_file, LOGO_FOLDER)

        side_path = ""
        if side_file and side_file.filename:
            side_path = save_upload(side_file, UPLOAD_FOLDER)

        drink_path = ""
        if drink_file and drink_file.filename:
            drink_path = save_upload(drink_file, UPLOAD_FOLDER)

        safe_user_folder = secure_filename(user_id) if user_id else "public"
        generated_items = []

        for format_key in outputs:
            filename = generate_social_visual(
                image_path=image_path,
                logo_path=logo_path,
                format_key=format_key,
                title=title,
                subtitle=subtitle,
                badge=badge,
                price=price,
                style=style,
                note=generation_note,
                campaign_goal=campaign_goal,
                side_path=side_path,
                drink_path=drink_path,
            )

            local_output_path = OUTPUT_FOLDER / filename
            local_image_url = output_url(filename)
            local_download_url = f"/download/{filename}"
            storage_key = f"{safe_user_folder}/{filename}"
            storage_url = upload_to_supabase_storage(str(local_output_path), storage_key)

            image_url = storage_url or local_image_url
            download_url = storage_url or local_download_url
            label = SOCIAL_OUTPUTS.get(format_key, {}).get("label", format_key)
            item_title = f"Social Media Kit - {label}"
            if title:
                item_title = f"{title} - {label}"

            save_design_to_supabase(
                user_id=user_id,
                user_email=user_email,
                image_url=image_url,
                download_url=download_url,
                visual_type="social_media",
                title=item_title,
            )

            increment_usage(user_id)

            generated_items.append({
                "format": format_key,
                "label": label,
                "filename": filename,
                "image_url": image_url,
                "download_url": download_url,
                "width": SOCIAL_OUTPUTS[format_key]["width"],
                "height": SOCIAL_OUTPUTS[format_key]["height"],
                "storage_uploaded": bool(storage_url),
            })

        updated_profile = get_or_create_profile(user_id, user_email)

        return jsonify({
            "success": True,
            "items": generated_items,
            "batch_count": len(generated_items),
            "bundle_download_url": bundle_download_url([item["filename"] for item in generated_items]),
            "quality_reports": [quality_report],
            "profile": updated_profile,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/recent", methods=["GET"])
def api_recent():
    return jsonify({
        "success": True,
        "items": list_recent_outputs(12),
    })

@app.route("/api/profile", methods=["GET"])
def api_profile():
    try:
        user_id = request.args.get("user_id", "").strip()
        email = request.args.get("email", "").strip()

        if not user_id:
            return jsonify({"success": False, "error": "Missing user_id"}), 400

        profile = get_or_create_profile(user_id, email)

        return jsonify({
            "success": True,
            "profile": profile,
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/my-designs", methods=["GET"])
def api_my_designs():
    try:
        user_id = request.args.get("user_id", "").strip()

        if not user_id:
            return jsonify({"success": False, "error": "Missing user_id"}), 400

        limit = request.args.get("limit", "12").strip()
        try:
            limit = max(1, min(int(limit), 100))
        except Exception:
            limit = 12

        return jsonify({
            "success": True,
            "items": list_user_designs(user_id, limit),
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/outputs/<path:filename>")
def outputs(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)


@app.route("/download/<path:filename>")
def download(filename):
    path = OUTPUT_FOLDER / filename

    if not path.exists():
        return jsonify({"success": False, "error": "File not found."}), 404

    return send_file(path, as_attachment=True, download_name=filename)


@app.route("/download-bundle")
def download_bundle():
    raw_files = request.args.get("files", "")
    include_jpg = request.args.get("jpg", "1") != "0"
    filenames = []

    for item in raw_files.split(","):
        safe_name = secure_filename(Path(item).name)
        if safe_name and safe_name not in filenames:
            filenames.append(safe_name)

    if not filenames:
        return jsonify({"success": False, "error": "No files selected."}), 400

    zip_buffer = io.BytesIO()
    added = 0

    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        manifest_lines = [
            "Food AI Studio Delivery Pack",
            "PNG files are original generated assets.",
            "JPG files are platform-friendly copies for merchant upload.",
            "",
        ]

        for filename in filenames:
            path = OUTPUT_FOLDER / filename
            if not path.exists() or not path.is_file():
                continue

            bundle.write(path, arcname=f"png/{filename}")
            manifest_lines.append(f"png/{filename}")
            added += 1

            if include_jpg and path.suffix.lower() == ".png":
                try:
                    with Image.open(path) as img:
                        jpg_io = io.BytesIO()
                        img.convert("RGB").save(jpg_io, format="JPEG", quality=92, optimize=True)
                        jpg_name = f"{path.stem}.jpg"
                        bundle.writestr(f"jpg/{jpg_name}", jpg_io.getvalue())
                        manifest_lines.append(f"jpg/{jpg_name}")
                except Exception as e:
                    manifest_lines.append(f"JPG conversion skipped for {filename}: {e}")

        bundle.writestr("README.txt", "\n".join(manifest_lines))

    if added == 0:
        return jsonify({"success": False, "error": "Selected files were not found."}), 404

    zip_buffer.seek(0)
    bundle_name = f"food-ai-delivery-pack-{int(time.time())}.zip"
    return send_file(zip_buffer, mimetype="application/zip", as_attachment=True, download_name=bundle_name)


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
        "supabase_service_configured": bool(SUPABASE_URL and SUPABASE_SERVICE_KEY),
        "supabase_storage_bucket": SUPABASE_STORAGE_BUCKET,
        "poster_size": f"{POSTER_W}x{POSTER_H}",
        "product_size": f"{PRODUCT_W}x{PRODUCT_H}",
        "banner_size": f"{BANNER_W}x{BANNER_H}",
        "platform_packs": PLATFORM_PACKS,
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")
