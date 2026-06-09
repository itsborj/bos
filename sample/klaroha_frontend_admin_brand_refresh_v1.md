# Klaroha Frontend/Admin Brand Refresh — Sample v1

Source of truth: Klaroha Brand Guidelines & Strategic Brief, Approved May 2026 v2.2.

## Color-use target

- Page / app / admin canvas: Pure White `#FFFFFF` only.
- App/admin layout uses a centered fixed container: `max-width: 1280px; width: 100%; margin: 0 auto;` so large screens do not overexpand.
- Standard card fill: Ivory `#F5F1E8` only as a card or secondary panel surface — never a page background.
- Linen `#F2E8D0`: secondary warm card, draft badge, print/section alternation only.
- Racing Green `#0B3D2E`: wordmark, headlines on light surfaces, active nav, structural chrome, and sparing hero/featured surfaces.
- Racing Green surfaces: Ivory headline/body, Light Gold labels, Warm Gold italic accent only.
- Copper `#B85C30`: every primary/task execution CTA (`Submit`, `Confirm`, `Create`, `Get started`, `Approve`, `Save`, `Send`, `New Campaign`) and occasional featured card/background. Copper surfaces always use Ivory text.
- Warm Gold `#826D40`: tagline, logo clarity dot, eyebrow/pull-quote accent only. Never paragraph/body copy and never status/live/error.
- Light Gold `#C8A870`: sublabels on dark/Racing Green surfaces or badge fill with dark text. Never foreground on white/ivory/linen.
- Obsidian `#080B0D`: cockpit/dashboard/footer/high-contrast sections only. Text must be Ivory / Light Gold / Warm Gold accent — never Racing Green.
- Oxblood `#7A2E2E`: error/failure/system alert only. On Obsidian use lightened Oxblood text if needed, not the anchor Oxblood.

## App shell sample

- Canvas is Pure White.
- Topbar is white with a 0.5px Racing Green-tinted border.
- Logo reads `KLAROHA` in Manrope 700, uppercase, `0.22em` tracking, Racing Green.
- Tagline appears as a small italic Warm Gold line: `Marketing, Engineered for Clarity.`
- Navigation active state is Racing Green text with a thin underline/rail, not a filled green button block.
- Brand selector is a 2px control: white fill, Racing Green text/border.
- Structural cards, Stream cards, and CMO AI messages default to Pure White with thin borders. Ivory/Linen are selective warm alternation surfaces only, not the default card background.
- Stream uses restraint: recommendations and artifact labels are white/transparent with thin Racing Green/Warm Gold/Oxblood rails or text. Avoid large colored panels except true status badges or deliberate cockpit sections.

## Admin sample

- Sidebar remains white, not ivory or dark.
- Navigation active state uses Racing Green text with a thin active rail/underline on white.
- Primary/task buttons use Copper fill with Ivory text — never Racing Green.
- Secondary buttons use transparent fill with Racing Green border/text.
- `.btn-accent` / Gold buttons are reserved for premium/upgrade only, not normal task execution.
- Dashboard stat strip is the only Obsidian cockpit moment; text is Ivory/Light Gold only.
- Admin cards default to Pure White with thin Racing Green-tinted borders and square corners. Use Ivory/Linen only for intentional warm secondary panels.

## Backend surfaces

- Public backend-rendered HTML, including calendar/booking widgets, must use the same map: white page, 1280px or narrow fixed container as appropriate, Manrope headings/labels, Inter body, Copper primary submit, active selections as Racing Green text/underline, square structural cards.

## Forbidden outcomes

- No full-page Ivory or Linen background.
- No blanket Ivory card background across the app; most structural cards stay Pure White.
- No Light Gold text on white/ivory/linen.
- No Warm Gold body paragraphs.
- No gold as status/live/error.
- No Racing Green text on Obsidian, Racing Green surfaces, or Copper surfaces.
- No dark text on Copper/Obsidian.
- No rounded cards, rounded panels, pill nav, circular avatars, or `border-radius > 2px` except tiny operational signal dots.
- No blue generic SaaS status styling for BOS-native cards.
