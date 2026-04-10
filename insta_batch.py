#!/usr/bin/env python3
"""TheDailyByte Batch Processor — Multi-Post Generation (Self-Healing)"""
import asyncio, json, logging, os, sys, traceback
from pathlib import Path

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(message)s")

# --- Self-healing imports ---
def _safe_import(module_path, name):
    try:
        mod = __import__(module_path, fromlist=[name])
        return getattr(mod, name)
    except Exception as e:
        logging.error(f"SELF-HEAL: Failed to import {name} from {module_path}: {e}")
        return None

generate_post_content = _safe_import("insta_pipeline", "generate_post_content")
create_instagram_image = _safe_import("insta_image_pro", "create_instagram_image")
optimize_caption = _safe_import("insta_seo", "optimize_caption")


def _fallback_content(topic, niche):
    """Emergency content when all imports/AI fail."""
    return {
        "headline": topic[:50],
        "subheadline": f"Essential {niche} insights",
        "points": [f"Key fact about {topic}", "Save this for later", "Share with someone who needs this"],
        "caption": f"Did you know? {topic}\n\nLike & save! #{niche} #dailybyte",
        "hashtags": [niche, "dailybyte", "facts", "trending"]
    }


def _fallback_image(content, path, niche):
    """Emergency image generation when insta_image_pro fails."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (1080, 1080), (15, 15, 30))
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        except:
            font = ImageFont.load_default()
        draw.text((80, 400), content.get("headline", "Daily Byte")[:30], fill=(255, 255, 255), font=font)
        img.save(path, quality=90)
        logging.info(f"SELF-HEAL: Fallback image saved to {path}")
    except Exception as e:
        logging.error(f"SELF-HEAL: Even fallback image failed: {e}")

BATCH_TOPICS = {
    "tech": ["AI agents", "Cloud computing", "DevOps tools", "API design", "Docker tips"],
    "health": ["Cold plunge", "Zone 2 cardio", "Sleep optimization", "Longevity science", "Metabolic health"]
}

def process_post(niche: str, topic: str, idx: int, output_dir: Path) -> dict:
    """Generate single Instagram post (self-healing)"""
    post_id = f"{niche}_{idx:03d}"
    log = logging.getLogger(post_id)
    
    try:
        log.info(f"[{idx}] START: {topic}")
        
        # 1. Content generation (with fallback)
        if generate_post_content:
            try:
                content = generate_post_content(topic, niche)
            except Exception as e:
                log.warning(f"SELF-HEAL: generate_post_content raised {e}, using fallback")
                content = _fallback_content(topic, niche)
        else:
            log.warning("SELF-HEAL: generate_post_content unavailable, using fallback")
            content = _fallback_content(topic, niche)
        
        # 2. Image creation (with fallback)
        image_path = output_dir / f"{post_id}.jpg"
        if create_instagram_image:
            try:
                create_instagram_image(content, str(image_path), niche)
            except Exception as e:
                log.warning(f"SELF-HEAL: create_instagram_image raised {e}, using fallback")
                _fallback_image(content, str(image_path), niche)
        else:
            log.warning("SELF-HEAL: create_instagram_image unavailable, using fallback")
            _fallback_image(content, str(image_path), niche)
        
        # 3. Caption optimization (with fallback)
        raw_caption = content.get("caption", f"Check out: {topic}")
        if optimize_caption:
            try:
                caption = optimize_caption(raw_caption, niche)
            except Exception as e:
                log.warning(f"SELF-HEAL: optimize_caption raised {e}, using raw caption")
                caption = raw_caption
        else:
            caption = raw_caption
        
        # 4. Save metadata
        metadata = {
            "post_id": post_id,
            "topic": topic,
            "headline": content.get("headline"),
            "caption": caption[:100] + "...",
            "image_path": str(image_path)
        }
        
        metadata_path = output_dir / f"{post_id}_meta.json"
        metadata_path.write_text(json.dumps(metadata, indent=2))
        
        log.info(f"[{idx}] COMPLETE: {post_id}")
        return {"status": "success", **metadata}
        
    except Exception as e:
        log.error(f"[{idx}] FAILED: {e}\n{traceback.format_exc()}")
        return {"status": "failed", "post_id": post_id, "error": str(e)}

def batch_process(niche: str, count: int):
    """Generate multiple posts sequentially"""
    output_dir = Path("./output/batch") / niche
    output_dir.mkdir(parents=True, exist_ok=True)
    
    topics = BATCH_TOPICS.get(niche, BATCH_TOPICS["tech"])
    results = []
    
    for i in range(count):
        topic = topics[i % len(topics)]
        result = process_post(niche, topic, i+1, output_dir)
        results.append(result)
    
    # Summary
    successes = sum(1 for r in results if r.get("status") == "success")
    failures = count - successes
    
    print(f"\n{'='*50}")
    print(f"BATCH COMPLETE: {niche.upper()}")
    print(f"Success: {successes}/{count}")
    print(f"Failures: {failures}")
    print(f"{'='*50}\n")
    
    # Save manifest
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2))
    print(f"✓ Manifest: {manifest_path}")
    
    return results

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--niche", default="tech", choices=["tech", "health"])
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()
    
    print(f"\n🚀 TheDailyByte BATCH MODE")
    print(f"Niche: {args.niche} | Posts: {args.count}\n")
    
    batch_process(args.niche, args.count)

if __name__ == "__main__":
    main()
