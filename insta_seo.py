#!/usr/bin/env python3
"""Instagram SEO — Viral Caption Optimization"""
import random, os, json
import google.generativeai as genai

# High-engagement hashtag clusters
HASHTAG_SETS = {
    "tech": [
        "#tech #technology #ai #coding #programming #developer #software #innovation #futuretech #techtrends",
        "#artificialintelligence #machinelearning #startup #automation #cloudcomputing #cybersecurity #datascience #techlife #devops",
        "#ai #aitools #chatgpt #generativeai #llm #automation #nocode #productivity #techstartup #saas"
    ],
    "health": [
        "#health #wellness #biohacking #longevity #fitness #nutrition #healthylifestyle #fitfam #healthtips #wellbeing",
        "#biohacker #coldplunge #zone2cardio #healthscience #longevityhacks #optimizehealth #fitnessmotivation #healthylife",
        "#healthoptimization #sleepscience #metabolichealth #antiaging #performancehealth #healthdata #sciencebased"
    ]
}

CAPTION_TEMPLATES = [
    "🚨 {hook}\n\n{body}\n\n💡 {cta}\n\n{hashtags}",
    "⚡ {hook}\n\n{body}\n\n👉 {cta}\n\n{hashtags}",
    "🔥 {hook}\n\n{body}\n\nDouble tap if you agree! 👇\n\n{hashtags}"
]

def optimize_caption(raw_caption: str, niche: str, use_ai: bool = True) -> str:
    """Generate viral Instagram caption"""
    
    # Fallback template
    hashtags = random.choice(HASHTAG_SETS.get(niche, HASHTAG_SETS["tech"]))
    template_caption = f"{raw_caption}\n\n{hashtags}"
    
    # Try AI enhancement
    if use_ai:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if api_key:
            try:
                genai.configure(api_key=api_key, transport="rest")
                model = genai.GenerativeModel("gemini-1.5-flash")
                
                prompt = f"""Create viral Instagram caption for: {raw_caption[:200]}
Niche: {niche}

Return JSON only:
{{
  "hook": "attention-grabbing first line with emoji (max 80 chars)",
  "body": "2-3 sentences of value (max 200 chars)",
  "cta": "clear call to action (max 60 chars)",
  "hashtags": "15-20 relevant hashtags"
}}"""
                
                resp = model.generate_content(prompt)
                text = resp.text.strip()
                if text.startswith("```"): text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"): text = text.rsplit("```", 1)[0]
                
                data = json.loads(text.strip())
                template = random.choice(CAPTION_TEMPLATES)
                ai_caption = template.format(
                    hook=data.get("hook", ""),
                    body=data.get("body", ""),
                    cta=data.get("cta", "Follow for more!"),
                    hashtags=data.get("hashtags", hashtags)
                )
                return ai_caption[:2200]  # Instagram limit
                
            except Exception as e:
                print(f"⚠ Caption AI failed: {e}, using template")
    
    return template_caption[:2200]

if __name__ == "__main__":
    import sys
    test = "Learn about AI automation in 2026"
    print(optimize_caption(test, "tech"))
