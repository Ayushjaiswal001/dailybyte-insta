import asyncio, json, os, subprocess, sys, tempfile, random, time, logging, requests
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import edge_tts
from functools import wraps

# Configure logging
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s - %(levelname)s - %(message)s")

def get_env_var(name, default=None):
    value = os.getenv(name)
    if value is None:
        logging.warning(f"Environment variable {name} not set. Using default: {default}")
        return default
    return value

# --- Configuration ---
GEMINI_API_KEY = get_env_var("GEMINI_API_KEY", "").strip()
INSTAGRAM_BUSINESS_ACCOUNT_ID = get_env_var("INSTAGRAM_BUSINESS_ACCOUNT_ID", "").strip()
INSTAGRAM_ACCESS_TOKEN = get_env_var("INSTAGRAM_ACCESS_TOKEN", "").strip()
PEXELS_API_KEY = get_env_var("PEXELS_API_KEY", "").strip()

OUTPUT_DIR = get_env_var("OUTPUT_DIR", "./output/insta")

TTS_VOICE = get_env_var("TTS_VOICE", "en-US-ChristopherNeural")
TTS_RATE = get_env_var("TTS_RATE", "+5%")

MAX_RETRIES = int(get_env_var("MAX_RETRIES", "3"))
RETRY_DELAY = int(get_env_var("RETRY_DELAY", "5"))

INSTA_IMAGE_RESOLUTION = "1080x1350"
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
FFMPEG_PRESET = "fast"

os.makedirs(OUTPUT_DIR, exist_ok=True)

BUILT_IN_TOPICS = {
    "tech": [
        {"topic": "The AI Secret Google Doesn't Want You to Know", "description": "Uncovering the hidden truth about AI agents.", "tags": ["ai", "google", "secret", "tech", "future"]},
        {"topic": "Why Your Phone is Actually Listening to You", "description": "The technical proof behind mobile eavesdropping.", "tags": ["privacy", "tech", "phone", "hacking", "safety"]},
        {"topic": "The 3-Minute Habit That Doubles Your IQ", "description": "A simple tech-driven habit for cognitive enhancement.", "tags": ["iq", "productivity", "tech", "brain", "habit"]},
    ],
    "kids": [
        {"topic": "The Secret Language of Talking Animals", "description": "A magical discovery in the forest.", "tags": ["kids", "story", "magic", "animals"]},
        {"topic": "Why the Moon Changes Shape Every Night", "description": "Fun moon phases explanation for kids.", "tags": ["kids", "science", "moon", "educational"]},
    ],
    "health": [
        {"topic": "The One Fruit That Reverses Aging (Science)", "description": "New research on longevity and nutrition.", "tags": ["health", "longevity", "aging", "nutrition"]},
        {"topic": "Cold Plunge Science — What Happens to Your Body", "description": "Real science behind cold water immersion", "tags": ["health", "coldplunge", "science", "biohacking"]},
    ],
}

current_insta_topic_index = 0

def retry(exceptions, tries=MAX_RETRIES, delay=RETRY_DELAY, backoff=2):
    def deco_retry(f):
        @wraps(f)
        def f_retry(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return f(*args, **kwargs)
                except exceptions as e:
                    logging.warning(f"{f.__name__} failed: {e}. Retrying in {mdelay}s...")
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return f(*args, **kwargs)
        return f_retry
    return deco_retry

def pick_topic(topic_arg, niche):
    global current_insta_topic_index
    if topic_arg and topic_arg.strip():
        return topic_arg.strip()
    niche_topics = BUILT_IN_TOPICS.get(niche, BUILT_IN_TOPICS["tech"])
    if not niche_topics:
        return f"Latest {niche} trends"
    topic_data = niche_topics[current_insta_topic_index % len(niche_topics)]
    current_insta_topic_index += 1
    logging.info(f"Picked built-in topic: {topic_data['topic']} for niche: {niche}")
    return topic_data['topic']

@retry(Exception)
def _generate_caption_gemini(topic, niche):
    api_key = GEMINI_API_KEY
    if not api_key:
        return None
    try:
        try:
            import google.genai as genai
        except ImportError:
            import google.generativeai as genai
        genai.configure(api_key=api_key.strip(), transport="rest")
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            f"Create an Instagram caption for a post about: {topic}. Niche: {niche}. "
            "1. Hook (first line): Curiosity-driven, max 15 words. "
            "2. Body (2-3 lines): Educational insight with pattern interrupt. "
            "3. CTA: Call to action (like, comment, save, follow). "
            "Return JSON only: { \"caption\", \"hashtags\": [] }."
        )
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"): text = text.split("\n",1)[1] if "\n" in text else text[3:]
        if text.endswith("```"): text = text.rsplit("```",1)[0]
        return json.loads(text.strip())
    except Exception as e:
        logging.error(f"Gemini caption generation failed: {e}")
        raise

def generate_caption(topic, niche):
    try:
        caption_data = _generate_caption_gemini(topic, niche)
        if caption_data: return caption_data
    except Exception as e:
        logging.warning(f"Gemini failed ({e}), falling back to template.")

    return {
        "caption": f"Did you know? {topic}\n\nMost people are missing this truth about {niche}. Like and save if you found this valuable!\n\n#mindblown #{niche}",
        "hashtags": [niche, "mindblown", "facts", "trending", "viral"]
    }

@retry(requests.exceptions.RequestException)
def upload_image_to_hosting(image_path):
    try:
        with open(image_path, "rb") as f:
            files = {"file": f}
            r = requests.post("https://catbox.moe/user/api.php", data={"reqtype": "fileupload"}, files=files, timeout=30)
            r.raise_for_status()
            url = r.text.strip()
            if url.startswith("http"):
                logging.info(f"Image hosted via catbox.moe: {url}")
                return url
    except Exception as e:
        logging.warning(f"catbox.moe upload failed: {e}, trying 0x0.st...")
    
    try:
        with open(image_path, "rb") as f:
            files = {"file": f}
            r = requests.post("https://0x0.st", files=files, timeout=30)
            r.raise_for_status()
            url = r.text.strip()
            if url.startswith("http"):
                logging.info(f"Image hosted via 0x0.st: {url}")
                return url
    except Exception as e:
        logging.warning(f"0x0.st upload failed: {e}")
    
    return None

def generate_image(topic, niche, output_path):
    img_width, img_height = 1080, 1350
    img = Image.new("RGB", (img_width, img_height), color=(30, 30, 35))
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    
    accent_color = (50, 150, 255)
    draw.rectangle([(0, 0), (img_width, 200)], fill=accent_color)
    
    y_pos = 50
    draw.text((50, y_pos), f"{niche.upper()}", fill=(255, 255, 255), font=body_font)
    
    y_pos = 250
    max_width = img_width - 100
    words = topic.split()
    lines = []
    current_line = []
    
    for word in words:
        current_line.append(word)
        line_text = " ".join(current_line)
        bbox = draw.textbbox((0, 0), line_text, font=title_font)
        line_width = bbox[2] - bbox[0]
        if line_width > max_width:
            current_line.pop()
            lines.append(" ".join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(" ".join(current_line))
    
    for line in lines:
        draw.text((50, y_pos), line, fill=(255, 255, 255), font=title_font)
        y_pos += 80
    
    y_pos = 1000
    draw.text((50, y_pos), "Swipe up for the full story", fill=(200, 200, 200), font=body_font)
    
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 80))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    
    img.save(output_path)
    logging.info(f"Image generated: {output_path}")

async def tts(text, path, voice, rate):
    await edge_tts.Communicate(text, voice, rate=rate).save(path)

@retry(Exception)
def upload_instagram(image_url, caption_text, hashtags):
    if not INSTAGRAM_BUSINESS_ACCOUNT_ID or not INSTAGRAM_ACCESS_TOKEN:
        logging.warning("Instagram credentials not set, skipping upload.")
        return
    
    caption = f"{caption_text}\n\n" + " ".join(f"#{tag}" for tag in hashtags)
    
    url = f"https://graph.instagram.com/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    params = {"access_token": INSTAGRAM_ACCESS_TOKEN}
    data = {"image_url": image_url, "caption": caption}
    
    try:
        r = requests.post(url, params=params, json=data, timeout=30)
        r.raise_for_status()
        media_id = r.json().get("id")
        logging.info(f"Posted to Instagram: {media_id}")
        
        publish_url = f"https://graph.instagram.com/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
        publish_data = {"creation_id": media_id}
        r = requests.post(publish_url, params=params, json=publish_data, timeout=30)
        r.raise_for_status()
        logging.info(f"Published to Instagram feed")
    except Exception as e:
        logging.error(f"Instagram upload failed: {e}")
        raise

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="")
    parser.add_argument("--niche", default="tech")
    args = parser.parse_args()
    
    topic = pick_topic(args.topic, args.niche)
    caption_data = generate_caption(topic, args.niche)
    
    logging.info("[1/4] Generating image...")
    image_path = Path(OUTPUT_DIR) / f"{topic.replace(' ', '_').replace('/', '')}.jpg"
    generate_image(topic, args.niche, str(image_path))
    
    logging.info("[2/4] Hosting image...")
    image_url = upload_image_to_hosting(str(image_path))
    if not image_url:
        logging.error("Failed to host image, aborting upload")
        return
    
    logging.info("[3/4] Preparing caption...")
    caption = caption_data.get("caption", f"Check out: {topic}")
    hashtags = caption_data.get("hashtags", [args.niche])
    
    logging.info("[4/4] Uploading to Instagram...")
    upload_instagram(image_url, caption, hashtags)
    
    logging.info("Instagram Pipeline Complete!")

if __name__=="__main__": main()
