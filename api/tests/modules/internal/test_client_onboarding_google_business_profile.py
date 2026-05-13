from __future__ import annotations

from capabilities.internal.client_onboarding.google_business_profile.module import GoogleBusinessProfileClientOnboardingModule


def test_template_renders_with_client_context() -> None:
    module = GoogleBusinessProfileClientOnboardingModule()
    prompt = module.build_prompt(
        {
            "client_name": "Acme Dental",
            "gbp_access_email": "gbp@example.com",
            "google_drive_folder_link": "https://drive.example/folder",
            "questionnaire_link": "https://forms.example/questionnaire",
            "kickoff_call_link": "https://cal.example/kickoff",
            "team_members": ["Ava - Account Manager - ava@example.com"],
            "signoff_name": "Sam",
        }
    )

    assert "Acme Dental" in prompt
    assert "gbp@example.com" in prompt
    assert "Google Business Profile" in prompt
    assert "ACCESS / LOGINS" in prompt


def test_self_check_passes_complete_email() -> None:
    module = GoogleBusinessProfileClientOnboardingModule()
    content = """Subject: Getting Started on your Google Business Profile

Hey Acme Dental,

Great to have you on board.

ACCESS / LOGINS
Please grant us access to your Google Business Profile using gbp@example.com. Your Google Drive folder is ready for all onboarding files.

DISCOVERY
Please complete the onboarding questionnaire, then schedule the kickoff call.

CREATIVES / MARKETING RESOURCES
Please share creatives including logos, promotional media, customer persona details, testimonials, business photos, and videos.

TEAM MEMBERS
Ava - Account Manager - ava@example.com

Thanks and regards,
Sam
"""

    verdict, failures = module.self_check(content, {"client_name": "Acme Dental"})

    assert verdict == "pass"
    assert failures == []


def test_self_check_fails_missing_operational_sections() -> None:
    module = GoogleBusinessProfileClientOnboardingModule()
    content = """Subject: Welcome

Hey Acme Dental,

Glad to work with you.
"""

    verdict, failures = module.self_check(content, {"client_name": "Acme Dental"})

    assert verdict == "fail"
    assert "missing_google_business_profile" in failures
    assert "missing_google_drive_folder" in failures
    assert "missing_questionnaire" in failures
    assert "missing_team_members" in failures


def test_module_info() -> None:
    module = GoogleBusinessProfileClientOnboardingModule()
    info = module.module_info()

    assert info["id"] == "internal.client_onboarding.google_business_profile"
    assert info["vertical"] == "internal"
    assert info["platform_hint"] == "google_business_profile_onboarding"
