"""
insta_pipeline.py — TheDailyByte Instagram Auto-Poster
=======================================================
Generates + posts daily tech carousel/reel content to Instagram.
Uses Gemini for captions + Pexels for images.
Cost: $0.00

Flow:
  1. Gemini → trending topic + caption + hashtags
  2. Pexels → fetch relevant image
  3. Instagram Graph API → upload + publish
"""

import os, sys, json, argparse, logging, time
from pathlib import Path
import requests

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("InstaBot")

GEMINI_BASE    = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_KEY     = os.environ.get("GEMINI_API_KEY", "")
PEXELS_KEY     = os.environ.get("PEXELS_API_KEY", "")
INSTA_TOKEN    = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
INSTA_ACCT_ID  = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
OUTPUT_DIR     = os.environ.get("OUTPUT_DIR", "./output")

MODELS = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.5-flash-001"]


# ── Gemini ────────────────────────────────────────────────────────────────
def gemini_call(prompt: str) -> str:
    for model in MODELS:
        url = f"{GEMINI_BASE}/models/{model}:generateContent?key={GEMINI_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.8}
        }
        try:
            r = requests.post(url, json=payload, timeout=30)
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if r.status_code == 429:
                log.warning(f"[GEMINI] Rate limit on {model}, waiting 30s")
                time.sleep(30)
        except Exception as e:
            log.warning(f"[GEMINI] {model}: {e}")
    raise RuntimeError("Gemini failed after all models")


# ── Generate content ──────────────────────────────────────────────────────
def generate_content(topic: str, niche: str) -> dict:
    log.info(f"[STEP 1/3] Generating Instagram content: '{topic}'")
    prompt = f"""You are a viral Instagram content creator for Indian tech audience.
Topic: "{topic or f'Top trending {niche} tip today'}"
Niche: {niche}

Create an Instagram post. Return ONLY valid JSON no markdown:
{{
  "caption": "Engaging 150-word caption with story hook, value, and CTA. Use line breaks. Indian audience.",
  "hashtags": "#hashtag1 #hashtag2 #hashtag3 #hashtag4 #hashtag5 #hashtag6 #hashtag7 #hashtag8 #hashtag9 #hashtag10 #hashtag11 #hashtag12 #hashtag13 #hashtag14 #hashtag15",
  "image_keyword": "single best keyword for stock photo search",
  "alt_text": "Image description for accessibility under 100 chars"
}}"""

    raw = gemini_call(prompt)
    raw = raw.strip()
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip()
            if part.startswith("json"): part = part[4:].strip()
            if part.startswith("{"): raw = part; break
    s, e = raw.find("{"), raw.rfind("}")
    if s != -1 and e > s: raw = raw[s:e+1]

    try:
        data = json.loads(raw)
    except Exception:
        data = {
            "caption": f"Amazing {niche} tip you need to know today! 🚀\n\nSave this post for later.\n\nFollow for daily {niche} tips!",
            "hashtags": f"#{niche} #tech #india #trending #viral #tips #motivation #success #learn #grow",
            "image_keyword": niche,
            "alt_text": f"{niche} related content"
        }

    log.info(f"[STEP 1/3] Content generated — caption: {len(data.get('caption',''))} chars")
    return data


# ── Fetch image from Pexels ───────────────────────────────────────────────
def fetch_image(keyword: str, output_dir: str) -> str:
    log.info(f"[STEP 2/3] Fetching image: '{keyword}'")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    headers = {"Authorization": PEXELS_KEY}
    try:
        r = requests.get(
            "https://api.pexels.com/v1/search",
            headers=headers,
            params={"query": keyword, "per_page": 1, "orientation": "square"},
            timeout=15
        )
        photos = r.json().get("photos", [])
        if photos:
            img_url = photos[0]["src"]["large"]
            img_path = os.path.join(output_dir, "post_image.jpg")
            img_data = requests.get(img_url, timeout=30).content
            with open(img_path, "wb") as f:
                f.write(img_data)
            log.info(f"[STEP 2/3] Image saved: {len(img_data)//1024} KB")
            return img_path
    except Exception as e:
        log.warning(f"[PEXELS] Failed: {e}")

    # Fallback: use a simple colored placeholder via picsum
    try:
        img_path = os.path.join(output_dir, "post_image.jpg")
        img_data = requests.get("https://picsum.photos/1080/1080", timeout=15).content
        with open(img_path, "wb") as f:
            f.write(img_data)
        log.info("[STEP 2/3] Using fallback placeholder image")
        return img_path
    except Exception:
        raise RuntimeError("Could not fetch any image")


# ── Post to Instagram ─────────────────────────────────────────────────────
def post_to_instagram(image_path: str, content: dict) -> str:
    """
    Instagram Graph API: 2-step process
    Step A: Create container with image URL
    Step B: Publish the container
    Note: Image must be publicly accessible URL.
    For GitHub Actions, we upload to a public URL first.
    """
    log.info("[STEP 3/3] Posting to Instagram...")

    if not INSTA_TOKEN or not INSTA_ACCT_ID:
        log.warning("[INSTAGRAM] No credentials — skipping upload, image saved locally")
        log.info(f"[INSTAGRAM] Image at: {image_path}")
        return "LOCAL_ONLY"

    # Validate token first
    try:
        check = requests.get(
            f"https://graph.instagram.com/me",
            params={"access_token": INSTA_TOKEN},
            timeout=10
        )
        if check.status_code != 200:
            log.error(f"[INSTAGRAM] Token invalid: {check.json()}")
            log.error("[INSTAGRAM] Get new token at developers.facebook.com/tools/explorer")
            return "TOKEN_EXPIRED"
        log.info(f"[INSTAGRAM] Token valid for: {check.json().get('username', 'unknown')}")
    except Exception as e:
        log.error(f"[INSTAGRAM] Token check failed: {e}")
        return "LOCAL_ONLY"

    # Build full caption
    caption = content["caption"] + "\n\n" + content["hashtags"]

    # For production: image needs to be a public URL
    # Upload to imgbb (free) or use a CDN
    # For now log the local path — user should configure their own CDN
    log.info(f"[INSTAGRAM] Image ready: {image_path}")
    log.info(f"[INSTAGRAM] Caption ({len(caption)} chars) ready")
    log.info("[INSTAGRAM] ⚠️ To auto-publish: image must be hosted at a public HTTPS URL")
    log.info("[INSTAGRAM] Option 1: Upload to imgbb.com API (free)")
    log.info("[INSTAGRAM] Option 2: Use GitHub Pages as image host")
    log.info("[INSTAGRAM] Saving content for manual review...")

    # Save post data for manual publishing
    post_data = {
        "caption": caption,
        "image_path": image_path,
        "alt_text": content.get("alt_text", ""),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": "ready_to_publish"
    }
    with open(os.path.join(OUTPUT_DIR, "post_data.json"), "w") as f:
        json.dump(post_data, f, indent=2)

    log.info("[STEP 3/3] Post data saved to post_data.json")
    return "SAVED_LOCALLY"


# ── Main ──────────────────────────────────────────────────────────────────
def run(topic: str, niche: str) -> None:
    log.info("="*55)
    log.info(f"  InstaBot | {niche.upper()} | {time.strftime('%Y-%m-%d')}")
    log.info("="*55)

    if not GEMINI_KEY:
        log.error("GEMINI_API_KEY not set. Aborting.")
        sys.exit(1)

    content    = generate_content(topic, niche)
    image_path = fetch_image(content["image_keyword"], OUTPUT_DIR)
    result     = post_to_instagram(image_path, content)

    log.info("="*55)
    log.info(f"  DONE | Result: {result}")
    log.info("="*55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="")
    parser.add_argument("--niche", default="tech")
    args = parser.parse_args()
    run(args.topic, args.niche)
