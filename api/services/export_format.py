"""Export formatting — format run content for easy copy-pasting to platforms.

Extracted from routers/runs.py _format_for_platform.
"""

import re


def format_for_platform(platform: str, content: str) -> dict:
    """Format content for easy copy-pasting based on platform."""

    if platform == "facebook":
        return {
            "type": "text",
            "content": content,
            "copy_paste": content,
            "instructions": "Copy and paste directly into Facebook Ads Manager",
        }

    elif platform == "twitter":
        return {
            "type": "text",
            "content": content,
            "copy_paste": content,
            "character_count": len(content),
            "max_chars": 280,
            "instructions": "Copy and paste directly into Twitter Ads",
        }

    elif platform == "google":
        headlines = re.findall(r"^Headline\s+\d+:\s*(.+)$", content, re.MULTILINE)
        descriptions = re.findall(r"^Description\s+\d+:\s*(.+)$", content, re.MULTILINE)

        return {
            "type": "google_rsa",
            "headlines": headlines,
            "descriptions": descriptions,
            "copy_paste": content,
            "instructions": "Copy each headline and description into the corresponding fields in Google Ads",
        }

    elif platform == "email":
        lines = content.split("\n")
        subject = ""
        body = content

        for line in lines:
            if line.lower().startswith("subject:"):
                subject = line[8:].strip()
                body = content[content.find("\n", content.find("Subject:")) + 1:].strip()
                break

        return {
            "type": "email",
            "subject": subject,
            "body": body,
            "full_email": content,
            "instructions": "Copy subject and body into your email client",
        }

    else:
        return {
            "type": "text",
            "content": content,
            "copy_paste": content,
            "instructions": "Copy and paste the content",
        }
