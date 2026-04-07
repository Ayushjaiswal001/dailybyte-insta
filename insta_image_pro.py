#!/usr/bin/env python3
"""Instagram Image Templates — Viral Designs"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import random, textwrap

TEMPLATES = {
    "minimal": {"bg": "#FFFFFF", "accent": "#000000", "text": "#1A1A1A"},
    "tech": {"bg": "#0F0F23", "accent": "#00D9FF", "text": "#FFFFFF"},
    "gradient": {"bg": "#FF6B6B", "accent": "#4ECDC4", "text": "#FFFFFF"},
    "pastel": {"bg": "#FFF4E6", "accent": "#FF6B6B", "text": "#2C3E50"}
}

def create_instagram_image(content: dict, output_path: str, niche: str = "tech"):
    """Generate viral Instagram post (1080x1080)"""
    
    # Choose template
    template_key = "tech" if niche == "tech" else random.choice(list(TEMPLATES.keys()))
    theme = TEMPLATES[template_key]
    
    # Create canvas
    img = Image.new("RGB", (1080, 1080), theme["bg"])
    draw = ImageDraw.Draw(img)
    
    # Add gradient overlay for non-minimal templates
    if template_key != "minimal":
        gradient = Image.new("RGB", (1080, 1080), theme["accent"])
        gradient = gradient.filter(ImageFilter.GaussianBlur(radius=300))
        img = Image.blend(img, gradient, alpha=0.2)
        draw = ImageDraw.Draw(img)
    
    # Load fonts
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 80)
        subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
        point_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 38)
    except:
        title_font = subtitle_font = point_font = ImageFont.load_default()
    
    y_pos = 100
    
    # Headline
    headline = content.get("headline", "Daily Byte")[:50]
    bbox = draw.textbbox((0, 0), headline, font=title_font)
    w = bbox[2] - bbox[0]
    x = (1080 - w) // 2
    
    # Stroke for readability
    for dx in [-2, 0, 2]:
        for dy in [-2, 0, 2]:
            draw.text((x+dx, y_pos+dy), headline, fill=theme["bg"], font=title_font)
    draw.text((x, y_pos), headline, fill=theme["text"], font=title_font)
    y_pos += 120
    
    # Subheadline
    subheadline = content.get("subheadline", "")[:80]
    if subheadline:
        wrapped = textwrap.fill(subheadline, width=28)
        for line in wrapped.split("\n"):
            bbox = draw.textbbox((0, 0), line, font=subtitle_font)
            w = bbox[2] - bbox[0]
            x = (1080 - w) // 2
            draw.text((x, y_pos), line, fill=theme["accent"], font=subtitle_font)
            y_pos += 60
    
    y_pos += 40
    
    # Points (bullet list)
    points = content.get("points", [])[:5]
    for i, point in enumerate(points):
        wrapped = textwrap.fill(f"• {point}", width=35)
        for line in wrapped.split("\n"):
            draw.text((100, y_pos), line, fill=theme["text"], font=point_font)
            y_pos += 50
        y_pos += 10
    
    # Footer badge
    badge_text = f"#{i+1} DAILY BYTE"
    draw.rectangle([(80, 980), (280, 1040)], fill=theme["accent"])
    bbox = draw.textbbox((0, 0), badge_text, font=subtitle_font)
    bw = bbox[2] - bbox[0]
    draw.text(((280-bw)//2 + 80, 995), badge_text, fill=theme["bg"], font=subtitle_font)
    
    # Save
    img.save(output_path, quality=95, optimize=True)
    print(f"✓ Instagram image: {output_path}")

if __name__ == "__main__":
    test = {
        "headline": "AI Secrets",
        "subheadline": "What they don't tell you",
        "points": ["Point 1", "Point 2", "Point 3"]
    }
    create_instagram_image(test, "test.jpg", "tech")
