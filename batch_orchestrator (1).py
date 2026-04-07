#!/usr/bin/env python3
"""YTAutoPilot Batch Orchestrator — Multi-Video Pipeline"""
import asyncio, json, logging, os, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from pipeline import generate_script, pick_topic, tts, master_audio, dl_pexels, assemble, upload_yt
from seo_optimizer import optimize_seo
from thumbnail_gen import create_thumbnail

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(message)s")

BATCH_CONFIG = {
    "tech": {"count": 3, "topics": ["AI agents", "Cloud costs", "Docker tips"]},
    "health": {"count": 2, "topics": ["Cold plunge", "Zone 2 cardio"]},
    "kids": {"count": 2, "topics": ["Talking animals", "Little star"]}
}

async def process_video(niche: str, topic: str, idx: int, output_base: Path):
    """Process single video with full pipeline"""
    video_id = f"{niche}_{idx:03d}"
    log = logging.getLogger(video_id)
    
    try:
        log.info(f"[{idx}] START: {topic}")
        
        # 1. Script
        script = generate_script(topic, niche)
        
        # 2. SEO optimization
        seo = optimize_seo(script.get("title", topic), niche, use_ai=True)
        
        # 3. TTS
        work_dir = output_base / video_id
        work_dir.mkdir(parents=True, exist_ok=True)
        raw_audio = work_dir / "raw.mp3"
        final_audio = work_dir / "audio.mp3"
        
        narration = " ".join(s["narration"] for s in script.get("sections", []))
        await tts(narration, str(raw_audio), os.getenv("TTS_VOICE", "en-US-ChristopherNeural"), "+5%")
        master_audio(str(raw_audio), str(final_audio))
        
        # 4. Video clips
        clips = []
        for i, section in enumerate(script.get("sections", [])[:5]):
            try:
                clip = dl_pexels(section.get("search_query", niche), str(work_dir), i)
                if clip: clips.append(clip)
            except Exception as e:
                log.warning(f"Clip {i} failed: {e}")
        
        # 5. Assemble
        video_path = work_dir / f"{video_id}.mp4"
        assemble(clips, str(final_audio), str(video_path))
        
        # 6. Thumbnail
        thumb_path = work_dir / "thumbnail.jpg"
        create_thumbnail(seo["title"], niche, str(thumb_path))
        
        # 7. Upload
        upload_yt(str(video_path), seo["title"], seo["description"], seo["tags"])
        
        log.info(f"[{idx}] COMPLETE: {video_id}")
        return {"status": "success", "video_id": video_id, "title": seo["title"]}
        
    except Exception as e:
        log.error(f"[{idx}] FAILED: {e}")
        return {"status": "failed", "video_id": video_id, "error": str(e)}

async def batch_process(niche: str, count: int, topics: list):
    """Process multiple videos in parallel"""
    output_base = Path("./output/batch") / niche
    output_base.mkdir(parents=True, exist_ok=True)
    
    tasks = []
    for i in range(count):
        topic = topics[i % len(topics)] if topics else pick_topic("", niche)
        tasks.append(process_video(niche, topic, i+1, output_base))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Summary
    successes = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "success")
    failures = len(results) - successes
    
    print(f"\n{'='*50}")
    print(f"BATCH COMPLETE: {niche.upper()}")
    print(f"Success: {successes}/{len(results)}")
    print(f"Failures: {failures}")
    print(f"{'='*50}\n")
    
    return results

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", default="tech", choices=["tech", "health", "kids"])
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--topics", nargs="*", default=[])
    args = parser.parse_args()
    
    config = BATCH_CONFIG.get(args.niche, BATCH_CONFIG["tech"])
    count = args.count or config["count"]
    topics = args.topics or config["topics"]
    
    print(f"\n🚀 YTAutoPilot BATCH MODE")
    print(f"Niche: {args.niche} | Videos: {count}\n")
    
    results = asyncio.run(batch_process(args.niche, count, topics))
    
    # Save manifest
    manifest_path = Path("./output/batch") / f"{args.niche}_manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2))
    print(f"✓ Manifest: {manifest_path}")

if __name__ == "__main__":
    main()
