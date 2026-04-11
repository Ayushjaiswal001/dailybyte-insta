import argparse, asyncio, json, os, subprocess, sys, tempfile, random, time, logging
from pathlib import Path
import edge_tts, requests
from functools import wraps

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s - %(levelname)s - %(message)s")

def get_env_var(name, default=None):
    value = os.getenv(name)
    if value is None:
        logging.warning(f"Environment variable {name} not set. Using default: {default}")
        return default
    return value

GEMINI_API_KEY = get_env_var("GEMINI_API_KEY", "").strip()
PEXELS_API_KEY = get_env_var("PEXELS_API_KEY", "").strip()
YT_CREDENTIALS_JSON = get_env_var("YT_CREDENTIALS_JSON", "").strip()

OUTPUT_DIR_SHORTS = get_env_var("OUTPUT_DIR_SHORTS", "./output/shorts")
TTS_VOICE = get_env_var("TTS_VOICE", "en-US-ChristopherNeural")
TTS_RATE_SHORTS = get_env_var("TTS_RATE_SHORTS", "+10%")
MAX_RETRIES = int(get_env_var("MAX_RETRIES", "3"))
RETRY_DELAY = int(get_env_var("RETRY_DELAY", "5"))

SHORTS_VIDEO_RESOLUTION = "1080x1920"
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
FFMPEG_PRESET = "fast"
YOUTUBE_CATEGORY_ID = get_env_var("YOUTUBE_CATEGORY_ID", "28")

os.makedirs(OUTPUT_DIR_SHORTS, exist_ok=True)

BUILT_IN_TOPICS = {
    "tech": [
        {"topic": "The AI Secret Google Doesn't Want You to Know", "tags": ["ai", "google", "secret", "tech", "future"]},
        {"topic": "Why Your Phone is Actually Listening to You (Proof)", "tags": ["privacy", "tech", "phone", "hacking", "safety"]},
        {"topic": "The 3-Minute Habit That Doubles Your IQ", "tags": ["iq", "productivity", "tech", "brain", "habit"]},
        {"topic": "The Hidden Cost of Cloud Computing in 2026", "tags": ["cloud", "aws", "costs", "devops", "infrastructure"]},
        {"topic": "Edge Computing vs Cloud — Which Wins", "tags": ["edge", "cloud", "latency", "iot", "computing"]},
        {"topic": "How GitHub Copilot Changed Coding Forever", "tags": ["copilot", "ai", "coding", "github", "productivity"]},
        {"topic": "Quantum Computing Breakthroughs Explained", "tags": ["quantum", "computing", "physics", "future", "science"]},
        {"topic": "Why Every Developer Should Learn Docker", "tags": ["docker", "containers", "devops", "development", "skills"]},
        {"topic": "The Rise of Local AI on Your Phone", "tags": ["ai", "local", "mobile", "llm", "privacy"]},
        {"topic": "Web Assembly Is Revolutionizing the Web", "tags": ["wasm", "web", "performance", "browsers", "coding"]},
    ],
    "kids": [
        {"topic": "The Secret Language of Talking Animals", "tags": ["kids", "story", "magic", "animals", "adventure"]},
        {"topic": "The Little Star Who Outshone the Sun", "tags": ["kids", "moral", "stars", "bedtime", "kindness"]},
        {"topic": "The Elephant Who Forgot His Birthday", "tags": ["kids", "elephant", "birthday", "friendship", "funny"]},
        {"topic": "Why the Moon Changes Shape Every Night", "tags": ["kids", "science", "moon", "educational", "space"]},
        {"topic": "The Brave Little Boat on the Big Ocean", "tags": ["kids", "adventure", "ocean", "courage", "boats"]},
    ],
    "health": [
        {"topic": "The One Fruit That Reverses Aging (Science)", "tags": ["health", "longevity", "aging", "nutrition", "science"]},
        {"topic": "Why Cold Plunges are Actually Dangerous (Warning)", "tags": ["health", "biohacking", "warning", "safety", "fitness"]},
        {"topic": "Cold Plunge Science — What Happens to Your Body", "tags": ["health", "coldplunge", "science", "biohacking", "recovery"]},
        {"topic": "Zone 2 Cardio — Exercise Doctors Recommend Most", "tags": ["health", "cardio", "exercise", "longevity", "fitness"]},
        {"topic": "Sleep Optimization — 5 Habits Backed by Research", "tags": ["health", "sleep", "habits", "research", "wellness"]},
    ],
}

current_short_topic_index = 0

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
    global current_short_topic_index
    if topic_arg and topic_arg.strip():
        return topic_arg.strip()
    niche_topics = BUILT_IN_TOPICS.get(niche, BUILT_IN_TOPICS["tech"])
    topic_data = niche_topics[current_short_topic_index % len(niche_topics)]
    current_short_topic_index += 1
    logging.info(f"Picked built-in topic: {topic_data['topic']} for niche: {niche}")
    return topic_data['topic']

@retry(Exception)
def _generate_short_script_gemini(topic, niche):
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
            f"Create a viral YouTube Shorts script about: {topic}. Niche: {niche}. "
            "1. HOOK (0-5s): Extreme curiosity gap. "
            "2. REVEAL (5-45s): High-pace educational content. "
            "3. CTA (45-60s): Urgency-driven subscribe. "
            'Return JSON only: { "title", "description", "tags": [], "narration_chunks": [ { "text", "search_query", "emotion" } ] }.'
        )
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith("```"): text = text.split("\n",1)[1] if "\n" in text else text[3:]
        if text.endswith("```"): text = text.rsplit("```",1)[0]
        return json.loads(text.strip())
    except Exception as e:
        logging.error(f"Gemini shorts script generation failed: {e}")
        raise

def generate_short_script(topic, niche):
    try:
        script = _generate_short_script_gemini(topic, niche)
        if script: return script
    except Exception as e:
        logging.warning(f"Gemini failed ({e}), falling back to template.")
    return {
        "title": f"The Truth About {topic} #Shorts",
        "description": f"Everything you need to know about {topic}. #{niche} #Shorts",
        "tags": [niche, "shorts", "viral"],
        "narration_chunks": [
            {"text": "Wait! Most people think this is just a trend.", "search_query": f"{niche} surprise", "emotion": "urgent"},
            {"text": f"But {topic} is actually changing everything right now.", "search_query": f"{niche} truth", "emotion": "authoritative"},
            {"text": f"The data shows {niche} is evolving faster than ever.", "search_query": f"{niche} proof", "emotion": "conversational"},
            {"text": "Like and subscribe if you found this valuable.", "search_query": f"{niche} success", "emotion": "friendly"},
        ]
    }

async def tts(text, path, voice, rate):
    await edge_tts.Communicate(text, voice, rate=rate).save(path)

def master_audio(input_path, output_path):
    try:
        filter_str = (
            "afftdn, "
            "acompressor=threshold=-20dB:ratio=4:attack=5:release=50, "
            "alimiter=limit=-1dB, "
            "loudnorm=I=-14:LRA=7:tp=-1"
        )
        subprocess.run([
            "ffmpeg", "-y", "-i", input_path,
            "-af", filter_str,
            "-c:a", "libmp3lame", "-b:a", "320k",
            output_path
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        Path(output_path).write_bytes(Path(input_path).read_bytes())

def get_dur(f):
    try:
        r = subprocess.run(["ffprobe","-v","quiet","-show_entries","format=duration","-of","csv=p=0",f], capture_output=True, text=True, check=True)
        return float(r.stdout.strip())
    except Exception:
        return 10.0

@retry(requests.exceptions.RequestException)
def dl_pexels_portrait(query, work_dir, idx):
    key = PEXELS_API_KEY
    if not key: return None
    headers = {"Authorization": key}
    params = {"query": query, "per_page": 3, "orientation": "portrait"}
    r = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=30)
    r.raise_for_status()
    vids = r.json().get("videos",[])
    if not vids: return None
    files = vids[idx%len(vids)].get("video_files",[])
    hd = [v for v in files if v.get("height",0)>=1280]
    chosen = (hd or files)[0] if files else None
    if not chosen: return None
    out_path = Path(work_dir) / f"clip_{idx}.mp4"
    out_path.write_bytes(requests.get(chosen["link"], timeout=60).content)
    return str(out_path)

def assemble_short(clips, audio_path, output_path):
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    dur = get_dur(audio_path)
    if not clips:
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s={SHORTS_VIDEO_RESOLUTION}:d={dur}",
            "-i", audio_path, "-c:v", VIDEO_CODEC, "-c:a", AUDIO_CODEC, "-shortest", output_path
        ], check=True, capture_output=True)
        return
    cpd = max(dur / len(clips), 3)
    trimmed_clips = []
    for i, clip_path in enumerate(clips):
        tp = Path(output_path).parent / f"t_{i}.mp4"
        vf = (
            f"scale=1200:-1, "
            f"zoompan=z='min(zoom+0.002,1.5)':d={int(cpd*30)}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={SHORTS_VIDEO_RESOLUTION}, "
            f"eq=saturation=1.1:contrast=1.1"
        )
        subprocess.run([
            "ffmpeg", "-y", "-i", clip_path, "-t", str(cpd),
            "-vf", vf,
            "-c:v", VIDEO_CODEC, "-preset", FFMPEG_PRESET, "-an", str(tp)
        ], check=True, capture_output=True)
        trimmed_clips.append(str(tp))
    concat_file = Path(output_path).parent / "concat.txt"
    concat_file.write_text("\n".join(f"file '{t.replace(chr(92), '/')}'" for t in trimmed_clips))
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
        "-i", audio_path, "-c:v", VIDEO_CODEC, "-c:a", AUDIO_CODEC,
        "-shortest", "-movflags", "+faststart", output_path
    ], check=True, capture_output=True)

def _get_yt_credentials():
    """Parse and refresh YouTube OAuth credentials. FAILS LOUD if anything is wrong."""
    if not YT_CREDENTIALS_JSON:
        logging.error("FATAL: YT_CREDENTIALS_JSON secret is EMPTY. Set it in GitHub Secrets.")
        logging.error("Video was generated and saved as artifact, but YouTube upload SKIPPED.")
        sys.exit(1)

    try:
        creds_data = json.loads(YT_CREDENTIALS_JSON)
    except json.JSONDecodeError as e:
        logging.error(f"FATAL: YT_CREDENTIALS_JSON is not valid JSON: {e}")
        sys.exit(1)

    required = ["client_id", "client_secret", "refresh_token"]
    missing = [k for k in required if not creds_data.get(k)]
    if missing:
        logging.error(f"FATAL: YT_CREDENTIALS_JSON missing fields: {missing}")
        logging.error(f"Keys present: {list(creds_data.keys())}")
        sys.exit(1)

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    creds = Credentials(
        token=creds_data.get("token"),
        refresh_token=creds_data["refresh_token"],
        token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"],
        scopes=creds_data.get("scopes", ["https://www.googleapis.com/auth/youtube.upload"])
    )

    logging.info("Refreshing YouTube OAuth token...")
    try:
        creds.refresh(Request())
        logging.info("YouTube token refreshed successfully.")
    except Exception as e:
        logging.error(f"FATAL: YouTube token refresh failed: {e}")
        logging.error("Your refresh_token may be revoked. Re-run get_youtube_token.py locally and update the secret.")
        sys.exit(1)

    return creds

@retry(Exception)
def upload_yt_short(video_path, title, description, tags):
    creds = _get_yt_credentials()
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    yt = build("youtube", "v3", credentials=creds)
    body = {
        "snippet": {"title": title[:100], "description": description[:5000], "tags": tags[:30], "categoryId": YOUTUBE_CATEGORY_ID},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    media = MediaFileUpload(video_path, chunksize=10*1024*1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            logging.info(f"Upload progress: {int(status.progress()*100)}%")
    video_id = resp.get("id", "UNKNOWN")
    logging.info(f"SUCCESS: Uploaded Short to YouTube: https://youtube.com/watch?v={video_id}")
    return video_id

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="")
    parser.add_argument("--niche", default="tech")
    args = parser.parse_args()

    topic = pick_topic(args.topic, args.niche)
    script = generate_short_script(topic, args.niche)
    chunks = script.get("narration_chunks", [])
    narration_text = " ".join(c["text"] for c in chunks)

    with tempfile.TemporaryDirectory() as wd_str:
        wd = Path(wd_str)
        raw_audio = wd / "raw_audio.mp3"
        mastered_audio = wd / "narration.mp3"

        logging.info("[1/5] Generating voiceover...")
        asyncio.run(tts(narration_text, str(raw_audio), TTS_VOICE, TTS_RATE_SHORTS))

        logging.info("[2/5] Mastering audio...")
        master_audio(str(raw_audio), str(mastered_audio))

        logging.info("[3/5] Downloading portrait clips...")
        clips = []
        for i, c in enumerate(chunks):
            clip = dl_pexels_portrait(c.get("search_query", args.niche), str(wd), i)
            if clip: clips.append(clip)

        logging.info("[4/5] Assembling short...")
        output_path = Path(OUTPUT_DIR_SHORTS) / f"{topic.replace(' ', '_').replace('/', '')}.mp4"
        assemble_short(clips, str(mastered_audio), str(output_path))
        logging.info(f"Short saved: {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")

        logging.info("[5/5] Uploading to YouTube...")
        upload_yt_short(
            str(output_path),
            script.get("title", topic),
            script.get("description", ""),
            script.get("tags", [])
        )

    logging.info("Shorts Pipeline Complete!")

if __name__ == "__main__":
    main()
