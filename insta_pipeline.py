#!/usr/bin/env python3
"""
TheDailyByte — Instagram Auto Post Pipeline
Generates an informative image post and publishes to Instagram via Graph API.
"""

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path

import google.generativeai as genai
import requests
from PIL import Image, ImageDraw, ImageFont


# ──────────────────────────────────────────────────
# 1. CONTENT GENERATION (Gemini)
# ──────────────────────────────────────────────────

def generate_post_content(topic: str, niche: str) -> dict:
    """Generate Instagram post content using Gemini AI."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")

    topic_part = f'about "{topic}"' if topic else f"trending in {niche}"

    prompt = f"""Create an Instagram carousel-style educational post {topic_part}.
Niche: {niche}

Return ONLY a JSON object with:
- "headline": bold attention-grabbing headline (max 50 chars)
- "subheadline": one-line hook (max 80 chars)  
- "points": array of 3-5 key facts/tips, each a short string (max 60 chars each)
- "caption": Instagram caption with emojis and 15 hashtags (max 2000 chars)
- "image_query": a Pexels search query for the background image
- "topic_used": the actual topic covered

Raw JSON only."""

    response = model.generate_content(prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]

    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return {
            "headline": f"{niche.title()} Daily Byte",
            "subheadline": f"Today's top {niche} insight",
            "points": [f"Key insight about {niche}"],
            "caption": f"Daily byte of {niche} knowledge! #{niche} #dailybyte #learning",
            "image_query": niche,
            "topic_used": topic or niche,
        }


# ──────────────────────────────────────────────────
# 2. IMAGE GENERATION
# ──────────────────────────────────────────────────

def download_pexels_image(query: str, output_path: str) -> bool:
    """Download a background image from Pexels."""
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        return False

    headers = {"Authorization": api_key}
    params = {"query": query, "per_page": 5, "orientation": "square"}
    try:
        resp = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=15)
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            return False

        img_url = photos[0]["src"]["large2x"]
        r = requests.get(img_url, timeout=30)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(r.content)
        return True
    except Exception as e:
        print(f"WARN: Pexels image download failed: {e}", file=sys.stderr)
        return False


def create_post_image(content: dict, output_path: str) -> str:
    """Create a styled Instagram post image."""
    W, H = 1080, 1080

    # Try to get background from Pexels
    bg_path = output_path + ".bg.jpg"
    has_bg = download_pexels_image(content.get("image_query", "technology"), bg_path)

    if has_bg:
        img = Image.open(bg_path).resize((W, H)).convert("RGBA")
        # Dark overlay for readability
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 180))
        img = Image.alpha_composite(img, overlay).convert("RGB")
        os.remove(bg_path)
    else:
        # Gradient background fallback
        img = Image.new("RGB", (W, H), (20, 20, 40))
        draw = ImageDraw.Draw(img)
        for y in range(H):
            r = int(20 + (y / H) * 30)
            g = int(20 + (y / H) * 10)
            b = int(40 + (y / H) * 60)
            draw.line([(0, y), (W, y)], fill=(r, g, b))

    draw = ImageDraw.Draw(img)

    # Use default font (monospace available on ubuntu-latest)
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 52)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except OSError:
        font_large = ImageFont.load_default()
        font_medium = font_large
        font_small = font_large

    # Draw headline
    headline = content.get("headline", "Daily Byte")
    wrapped = textwrap.fill(headline, width=25)
    draw.text((60, 120), wrapped, fill=(255, 255, 255), font=font_large)

    # Draw subheadline
    sub = content.get("subheadline", "")
    draw.text((60, 280), sub, fill=(200, 200, 255), font=font_medium)

    # Draw separator
    draw.line([(60, 340), (W - 60, 340)], fill=(100, 100, 200), width=2)

    # Draw bullet points
    y_pos = 380
    for point in content.get("points", [])[:5]:
        wrapped_point = textwrap.fill(f"→ {point}", width=38)
        draw.text((60, y_pos), wrapped_point, fill=(230, 230, 250), font=font_small)
        line_count = len(wrapped_point.split("\n"))
        y_pos += 40 * line_count + 20

    # Draw footer / brand
    draw.text((60, H - 100), "TheDailyByte", fill=(150, 150, 200), font=font_medium)
    draw.text((60, H - 55), "Follow for daily insights ✦", fill=(120, 120, 170), font=font_small)

    img.save(output_path, "JPEG", quality=95)
    print(f"  Image saved: {output_path}")
    return output_path


# ──────────────────────────────────────────────────
# 3. INSTAGRAM PUBLISH (Graph API)
# ──────────────────────────────────────────────────

def post_to_instagram(image_url: str, caption: str) -> bool:
    """Publish image to Instagram via Graph API (requires hosted image URL)."""
    access_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID")

    if not access_token or not account_id:
        print("WARN: Instagram credentials not set, skipping post", file=sys.stderr)
        return False

    base_url = f"https://graph.facebook.com/v21.0/{account_id}"

    try:
        # Step 1: Create media container
        create_resp = requests.post(f"{base_url}/media", data={
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token,
        }, timeout=30)
        create_resp.raise_for_status()
        creation_id = create_resp.json().get("id")

        if not creation_id:
            print("ERROR: No creation_id returned", file=sys.stderr)
            return False

        # Step 2: Publish
        publish_resp = requests.post(f"{base_url}/media_publish", data={
            "creation_id": creation_id,
            "access_token": access_token,
        }, timeout=30)
        publish_resp.raise_for_status()
        media_id = publish_resp.json().get("id")
        print(f"  ✓ Posted to Instagram! Media ID: {media_id}")
        return True

    except Exception as e:
        print(f"ERROR: Instagram post failed: {e}", file=sys.stderr)
        return False


def upload_image_to_hosting(image_path: str) -> str | None:
    """
    Instagram Graph API needs a publicly accessible URL.
    We use the Pexels image directly if available, or skip posting.
    For production, use Cloudinary/S3/Firebase Storage.
    """
    # For CI: use a temp image hosting approach
    # The workflow should ideally upload to a CDN first
    # For now, we'll note that the image was generated locally
    print("  NOTE: Image generated locally. For Instagram posting,")
    print("  configure a CDN (Cloudinary/S3) for public image hosting.")
    return None


# ──────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="TheDailyByte Instagram Pipeline")
    parser.add_argument("--topic", default="", help="Post topic (blank=auto)")
    parser.add_argument("--niche", default="tech", help="Content niche")
    args = parser.parse_args()

    output_dir = os.environ.get("OUTPUT_DIR", "./output")
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"  TheDailyByte — Instagram Pipeline")
    print(f"  Niche: {args.niche}")
    print(f"{'='*50}\n")

    # Step 1: Generate content
    print("[1/3] Generating post content with Gemini...")
    content = generate_post_content(args.topic, args.niche)
    print(f"  Headline: {content.get('headline', 'N/A')}")

    # Step 2: Create image
    print("\n[2/3] Creating post image...")
    image_path = os.path.join(output_dir, "post.jpg")
    create_post_image(content, image_path)

    # Step 3: Post to Instagram
    print("\n[3/3] Publishing to Instagram...")
    caption = content.get("caption", "")
    image_url = upload_image_to_hosting(image_path)

    if image_url:
        post_to_instagram(image_url, caption)
    else:
        print("  Image generated but not posted (no CDN configured).")
        print(f"  Caption:\n{caption[:200]}...")

    print("\n✓ Pipeline complete!")


if __name__ == "__main__":
    main()
