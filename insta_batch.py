#!/usr/bin/env python3
"""TheDailyByte Batch Processor — Multi-Post Generation"""
import asyncio, json, logging, os
from pathlib import Path
from insta_pipeline import generate_post_content
from insta_image_pro import create_instagram_image
from insta_seo import optimize_caption

logging.basicConfig(level="INFO", format="%(asctime)s [%(levelname)s] %(message)s")

BATCH_TOPICS = {
    "tech": ["AI agents", "Cloud computing", "DevOps tools", "API design", "Docker tips"],
    "health": ["Cold plunge", "Zone 2 cardio", "Sleep optimization", "Longevity science", "Metabolic health"]
}

def process_post(niche: str, topic: str, idx: int, output_dir: Path) -> dict:
    """Generate single Instagram post"""
    post_id = f"{niche}_{idx:03d}"
    log = logging.getLogger(post_id)
    
    try:
        log.info(f"[{idx}] START: {topic}")
        
        # 1. Content generation
        content = generate_post_content(topic, niche)
        
        # 2. Image creation
        image_path = output_dir / f"{post_id}.jpg"
        create_instagram_image(content, str(image_path), niche)
        
        # 3. Caption optimization
        caption = optimize_caption(content.get("caption", ""), niche)
        
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
        log.error(f"[{idx}] FAILED: {e}")
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
