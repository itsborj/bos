# International SEO Reference

Use only when the audited site serves multiple languages or regions.

## Hreflang

Check for self-referencing entries, reciprocal links, valid language/region codes, `x-default`, indexable 200-status target URLs, and no duplicate language-region codes pointing at different URLs.

Common failures:
- Missing self-reference causes the set to be ignored.
- One-directional hreflang pairs are dropped.
- Invalid codes such as `en-UK`; use `en-GB`.
- Hreflang targets are non-canonical, redirected, blocked, or 404.
- HTML and sitemap annotations disagree.

## Canonicalization

Each locale should self-canonical. Never canonical locale pages to a different-language equivalent; that suppresses the non-canonical locale. Canonical URLs must appear in the hreflang set.

## International Sitemaps

Use `xmlns:xhtml`; include all alternates including self and `x-default`; use absolute URLs. For many locales, split by content type and watch the 50MB size limit.

## Locale URL Structure

Recommended: subdirectories such as `/en/` and `/ar/`. Avoid `?lang=en`. Do not depend on IP or Accept-Language negotiation for Googlebot.

## Content Quality Across Locales

Translate main content, titles, descriptions, and headings — not just UI chrome. Do not create thin locale pages that cannot be genuinely useful.
