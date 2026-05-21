---
seat: c1
display_name: "Council Member 1"
status: vacant      # vacant | active | suspended

model:
  provider: openrouter
  model_id: ~        # set at recruitment

tools: []            # granted at recruitment

ideology: ~          # the worldview and priors that define this seat — set at recruitment

# Recruitment checklist:
#   1. Set display_name to the council member's identity
#   2. Set status: active
#   3. Set model.model_id (e.g. openai/gpt-4o, anthropic/claude-opus-4-5, google/gemini-pro-1.5)
#   4. Write ideology — the strategic worldview this seat brings
#   5. Grant tools if this seat needs data access
---
