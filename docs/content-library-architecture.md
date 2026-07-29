# Content Library Architecture

> Status: Design discussion — prototype pending. Do not wire into BOS until prototype is stress-tested.

---

## The Core Principle

Content and presentation are separate concerns. The database holds structured content as rows. The renderer decides what it looks like. AI fills the rows — it never touches the layout.

**AI is a form-completion engine, not a page-generation engine.**

---

## Mental Model: PostgreSQL as Filing Cabinet

| Analogy | PostgreSQL concept |
|---|---|
| Filing cabinet | Schema (`content.*`) |
| Labeled drawer | Table (`content.heroes`) |
| Folder template | Column definitions + constraints |
| Individual folder | Row |
| Window request | `SELECT` query |
| Ordered card stack | `page_sections` with `position` |
| Card type | `section_type` column |

---

## Schema Pattern: JSONB Overflow

Every content type table has a stable typed core plus a `meta JSONB` overflow column for fields that haven't stabilized yet.

```sql
CREATE TABLE content.heroes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  headline    TEXT NOT NULL,          -- max 8 words
  tagline     TEXT,                   -- max 15 words
  body        TEXT,                   -- 2 sentences
  cta_primary VARCHAR(50),            -- verb-first, max 4 words
  cta_secondary VARCHAR(50),
  tone        VARCHAR(30),
  campaign_type VARCHAR(50),
  created_at  TIMESTAMPTZ DEFAULT now(),
  meta        JSONB DEFAULT '{}'      -- overflow: sparse/experimental fields
);
```

**Field lifecycle:**
1. New field lands in `meta` first
2. If it appears on >80% of rows and is queried regularly, promote to a real column
3. Migration backfills existing rows from `meta`, drops the key from `meta`

This avoids premature schema commitment while keeping core fields typed, indexed, and constrained.

**Index `meta` for queryability:**
```sql
CREATE INDEX idx_heroes_meta ON content.heroes USING GIN (meta);
```

---

## AI as Typesetter

The operator speaks natural language. The system resolves it to a structured content model. AI fills the fields. PostgreSQL stores the row. The renderer produces the artifact.

**Operator input:**
```
"Write me a hero section for a memorial park campaign"
```

**What actually happens:**

```
Intent layer  →  resolves content_type: "hero", campaign_type: "memorial"
                 ↓
Schema layer  →  pulls hero content model + constraints
                 ↓
AI            →  fills the fields (form completion, not page generation)
                 ↓
PostgreSQL    →  stores the row
                 ↓
Renderer      →  produces the artifact
                 ↓
Operator      →  sees the finished hero section
```

**The AI prompt is a structured form, not a creative brief:**
```json
Fill this content model:
{
  "headline": "",        // max 8 words, urgency-forward
  "tagline": "",         // max 15 words, emotional resonance
  "body": "",            // 2 sentences, benefit-led
  "cta_primary": "",     // verb-first, max 4 words
  "cta_secondary": "",   // softer alternative, max 4 words
  "tone": "reverent",
  "campaign_type": "memorial"
}
```

The schema carries the editorial policy. Constraints live in the form definition, not in the prompt conversation.

---

## The Content Library: Compound Interest

Every approved artifact row is a library entry. Nothing is ephemeral — even throwaway campaigns deposit into the library.

Six months of fills means:
```sql
SELECT headline, cta_primary, conversion_rate
FROM content.heroes
WHERE campaign_type = 'memorial'
ORDER BY conversion_rate DESC
LIMIT 10;
```

High-performing rows feed back into the next generation as examples. The typesetter improves because the library compounds.

**Retrieval-first principle:** Before generating, query the library. If a matching approved row exists, surface it. Generate only on cache miss or explicit "create new" intent.

---

## Polymorphic Page Assembly

Pages are assembled from ordered content rows via a join table:

```sql
CREATE TABLE content.pages (
  id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug  VARCHAR(100) UNIQUE NOT NULL,
  title TEXT
);

CREATE TABLE content.page_sections (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  page_id      UUID REFERENCES content.pages(id),
  position     SMALLINT NOT NULL,
  section_type VARCHAR(50) NOT NULL,  -- "hero", "testimonial", "cta"
  content_id   UUID NOT NULL           -- FK to the relevant content table
);
```

The renderer iterates sections in order, reads `section_type`, fetches the row from the appropriate table by `content_id`, and renders the matching component.

**Polymorphism options** (choose based on how stable content types are):

| Option | Approach | Tradeoff |
|---|---|---|
| Separate nullable FKs | One FK column per type, only one populated | Clean integrity, unwieldy at scale |
| Untyped `content_id` UUID | App resolves table from `section_type` | Flexible, no DB-enforced referential integrity |
| Inline JSONB | Content embedded in section row | No join, loses relational integrity |

Separate nullable FKs or untyped UUID are the production-viable choices. EAV (entity-attribute-value) is not an option.

---

## Scales to All Content Types

The intent layer is a routing table. Every new content type is a new schema + a new route entry. The intent layer, AI fill, storage, and render steps don't change.

| Intent | Routes to |
|---|---|
| "hero section" | `content.heroes` |
| "testimonial" | `content.testimonials` |
| "email campaign" | `content.email_campaigns` |
| "social caption" | `content.social_posts` |
| "show analytics" | Query, not AI fill |
| "use an image" | `content.media` (retrieve or generate) |

Analytics are observation rows, not generation rows — same schema pattern, different data source.

Media (images, video) follow the same pointer model:
```sql
CREATE TABLE content.media (
  id            UUID PRIMARY KEY,
  url           TEXT NOT NULL,     -- S3, R2, etc.
  alt_text      TEXT,
  tags          TEXT[],
  campaign_type VARCHAR(50),
  meta          JSONB DEFAULT '{}'
);
```

---

## Relationship to BOS

BOS already has this architecture partially in place:

| BOS concept | Content library equivalent |
|---|---|
| `execution_brief` | Structured form AI fills |
| Module `execute()` | AI fill step |
| `PluginRun` / `Artifact` | Output row |
| `StreamArtifactCard` | Renderer |

The missing layer: **approved artifact fields promoted to a queryable content library.** Currently runs are ephemeral — approved or dismissed. The content library wires the "throwaway that performed" back into the next generation.

---

## Prototype Scope

Before incorporating into BOS, validate with a standalone prototype:

1. Schema with JSONB overflow on a single content type (`heroes`)
2. AI fill — Claude completes the structured form, result inserts into the table
3. Query patterns — JSONB vs column performance, GIN index behaviour
4. Field graduation — promote a `meta` key to a real column, migrate existing rows in place
5. Stress insert — bulk seed rows, benchmark query perf at 10k / 100k rows

**Stack:** Postgres (standalone docker-compose) + Python script. No FastAPI needed for the prototype — validate the data layer first.
