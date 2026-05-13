from __future__ import annotations

from capabilities.marketing.channel.google_business_profile.organic.posts.ideas.module import GoogleBusinessProfilePostIdeasModule


def test_template_renders_with_business_context() -> None:
    module = GoogleBusinessProfilePostIdeasModule()
    prompt = module.build_prompt({"brand_name": "Acme Dental", "product_name": "Dental Implants", "audience": "local patients"})

    assert "Acme Dental" in prompt
    assert "Dental Implants" in prompt
    assert "Google Business Profile" in prompt
    assert "Recommended Post Ideas" in prompt


def test_self_check_passes_valid_post_ideas() -> None:
    module = GoogleBusinessProfilePostIdeasModule()
    content = """## Recommended Post Ideas for Google Business Profile

Idea 1: Dental Implant FAQ
Category: Educational
Checklist Tactic: Share a short FAQ list
Post Angle: Answer common questions about Dental Implants for local patients.
Suggested Media: Dentist photo
CTA: Book

Idea 2: Before and After Smile
Category: Educational
Checklist Tactic: Share before-and-after project results
Post Angle: Show how Dental Implants restored confidence.
Suggested Media: Approved before/after image
CTA: Learn more

Idea 3: Meet the Team
Category: Company Introduction
Checklist Tactic: Introduce team members
Post Angle: Introduce the implant coordinator.
Suggested Media: Team photo
CTA: Call

Idea 4: Patient Review Spotlight
Category: Product or Service
Checklist Tactic: Share Google reviews
Post Angle: Highlight a happy Dental Implants patient review.
Suggested Media: Review screenshot
CTA: Get directions

Idea 5: Holiday Hours Reminder
Category: Product or Service
Checklist Tactic: Share updated opening hours
Post Angle: Remind patients when Dental Implants consultations are available.
Suggested Media: Clinic exterior
CTA: Message
"""

    verdict, failures = module.self_check(content, {"product_name": "Dental Implants"})

    assert verdict == "pass"
    assert failures == []


def test_self_check_fails_too_few_ideas() -> None:
    module = GoogleBusinessProfilePostIdeasModule()
    content = """## Recommended Post Ideas for Google Business Profile

Idea 1: Dental Tip
Category: Educational
Post Angle: Share a Dental Implants tip.
CTA: Learn more
"""

    verdict, failures = module.self_check(content, {"product_name": "Dental Implants"})

    assert verdict == "fail"
    assert "too_few_post_ideas" in failures


def test_module_info() -> None:
    module = GoogleBusinessProfilePostIdeasModule()
    info = module.module_info()

    assert info["id"] == "marketing.channel.google_business_profile.organic.posts.ideas"
    assert info["vertical"] == "marketing"
    assert info["platform_hint"] == "google_business_profile_posts"
