# Klaroha UI Mapping — Reference Implementation

Source reference: `http://localhost:8787/klaroha.html`.

## Containers

- Global shell: `max-width: 1280px; width: 100%; margin: 0 auto;`.
- Default page/card surface: Pure White `#FFFFFF` with `.5px solid rgba(11,61,46,.15)`.
- Ivory `#F5F1E8` and Linen `#F2E8D0` are selective warm alternation surfaces only, not default panels.
- Obsidian `#080B0D` is reserved for dashboard/cockpit metric strips.
- Cards/panels/modals/tables: `border-radius: 0`.
- Buttons/inputs/badges/tooltips: `border-radius: 2px` max.

## Color Relationships

### Light surfaces: White / Ivory / Linen
- Headline: Racing Green `#0B3D2E`.
- Body: `#2C4A3E`.
- Meta: `#4A6B5C`.
- Eyebrow/accent: Warm Gold `#826D40` or Copper on Linen.
- Never use Ivory, Linen, Light Gold, or white as foreground.

### Dark surfaces: Obsidian / Racing Green / Copper
- Primary foreground: Ivory `#F5F1E8`.
- Labels: Light Gold `#C8A870`.
- Warm Gold: subtitle/italic/accent only.
- Never use Racing Green, ink-body, ink-muted, Oxblood, or Copper as text on dark surfaces.

## Actions and Active State

- Primary task execution button: Copper `#B85C30`; hover `#964926`; text Ivory.
- Secondary button: transparent; Racing Green border/text.
- Ghost button: transparent; muted border/text.
- Gold button: reserved premium/upgrade only.
- Active links/nav: Racing Green text + thin underline/left rail. Do not use filled green nav pills.

## Typography

- Display/headlines/labels/metric numbers: Manrope.
- Body/UI/data: Inter.
- Wordmark: Manrope 700, uppercase, `0.22em` tracking.
- Eyebrows: Manrope 700, uppercase, tracked, Warm Gold on light surfaces.

## Frontend Applied Surfaces

- App/Admin shell: fixed centered `1280px` container.
- Stream/CMO: white structural surfaces, thin borders/rails, color as text/accent/status only.
- Gmail artifacts: native EmailPreview with white surface, square geometry, Racing Green subject, ink-body copy.

## Backend Applied Surfaces

- Public calendar booking widget uses the same token relationships, Copper primary submit, link-style active dates/slots, white structural surfaces, and 2px max radius.
