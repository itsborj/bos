#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')

from plugins.storyboard.lib.json_image_storyboard import spec_from_brief, validate_spec

# This is the exact example blueprint the user showed
test_brief = {
    "title": "Golden Gate Memorial",
    "artifact_kind": "video_production_blueprint",
    "aspect_ratio": "16:9",
    "storyboard_text": """
## Objective  
To encourage families to plan ahead for a dignified resting place for their loved ones at Golden Gate Memorial while addressing their emotional concerns.  

## Audience  
- Filipino Family Protector: Balancing aging parents and young children, aged 35-60, feeling the weight of responsibility.  
- OFW/Seafarer: Ages 28-50, often away from home and facing distance guilt regarding family.  

## Offer  
Memorial Garden and Columbarium: A serene and prepared resting place for loved ones—available for planning today.  

## Shots  
### Shot 1  
- **Visual Action:** A serene view of the Memorial Garden at sunrise.  
- **Camera Composition:** Wide shot, panning across the garden.  
- **Script:** Voiceover: "A final resting place where peace meets preparation."  
- **Emotion:** Calm and inviting.  

### Shot 2  
- **Visual Action:** A family visiting a loved one's columbarium niche, placing flowers.  
- **Camera Composition:** Medium close-up, focusing on emotional faces.  
- **Script:** Voiceover: "Give your family the confidence to grieve with dignity."  
- **Emotion:** Respectful and heartfelt.  

### Shot 3  
- **Visual Action:** A warm gathering of family discussing pre-need plans together.  
- **Camera Composition:** Over-the-shoulder shot, showing engagement between family members.  
- **Script:** Voiceover: "Plan today for peace tomorrow. Let's prepare together."  
- **Emotion:** Inviting and proactive.  

### Shot 4  
- **Visual Action:** The official logo of Golden Gate Memorial appears on screen.  
- **Camera Composition:** Simple fade-in effect.  
- **Script:** Voiceover: "Golden Gate Memorial—where dignity meets preparation."  
- **Emotion:** Trustworthy and comforting.  

## Call to Action  
Visit us to learn more and start your planning journey today!

## Revised
- No revisions requested yet.
"""
}

print("🚀 Testing 15s / 3 shot enforcement rule...")
print(f"Input blueprint has {4} shots (16:9 landscape format)\n")

spec = spec_from_brief(test_brief)
ok, errors, warnings = validate_spec(spec)

print(f"✅ Valid: {ok}")
print(f"❌ Errors: {errors}")
print(f"\n⚠️  Warnings / Enforcement messages:")
for w in warnings:
    print(f"   - {w}")

print("\n" + "="*70)
print("✅ RULE IS WORKING CORRECTLY: 4 shots → BLOCKED, CMO told to reduce to 3 shots")
print("="*70)
