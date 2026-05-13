from __future__ import annotations

from module_base import ModuleBase


class Copywriting30SecondMiloFrankModule(ModuleBase):
    id = "copywriting.copywriting_30_second_milo_frank"
    name = "copywriting_30_second_milo_frank"
    vertical = "copywriting"
    capability = "marketing.copywriting"
    platform_hint = "copywriting_skill"
    policy_default = "balanced"
    template = "copywriting/copywriting_30_second_milo_frank/template.j2"
    internal = True
    copywriting_skills = ["copywriting.copywriting_30_second_milo_frank"]

    prompt_guidance = """
### copywriting_30_second_milo_frank — The 30-Second Message

Use this reusable copywriting module whenever writing, editing, compressing, or strengthening persuasive copy that must make a point quickly: ads, emails, landing pages, pitches, sales scripts, bios, intros, presentations, memos, voicemails, and executive recommendations.

Core principle: the heart of the message must be understood, remembered, and acted on in about 30 seconds. Longer copy may add context and proof, but the central point must survive a distracted reader.

#### Seven required elements
1. Objective — one clear result the copy must produce.
2. Audience — the real decision-maker or listener with power to click, buy, reply, approve, attend, refer, or remember.
3. Approach — the strategic angle most likely to connect the objective to the audience's self-interest.
4. Hook — the first line, image, contrast, claim, question, or scene that earns attention.
5. Subject — only the essential benefit, mechanism, proof, differentiator, objection handling, or action details.
6. Ask — the specific action or response requested, with timing and friction level when useful.
7. Memorability — concrete imagery, clarity, personalization, and emotion that make the message stick.

#### Non-negotiables
- Use one primary objective. Do not chase multiple goals.
- Write for the decision-maker or real audience, not a generic reader.
- Lead with the listener's interest, not the sender's internal process.
- Make the point quickly before adding support.
- Include a clear ask unless the strategy deliberately calls for a softer reaction.
- Prefer concrete language, images, examples, and outcomes over abstractions.
- Cut anything that does not introduce, reinforce, prove, or advance the objective.
- Keep the copy natural; concise should not sound robotic.

#### Default workflow
- Objective: write the sentence "I want this audience to ___ because ___" and reduce it to one objective.
- Audience: translate "We want ___, but the audience wants ___; the copy must connect those two things."
- Approach: choose one controlling angle, such as outcome-first, problem-solution, opportunity, risk-reduction, identity, contrast, proof-led, or story-led.
- Hook: open with a relevant question, supportable claim, specific result, surprising contrast, miniature scene, direct stakes, or pattern interrupt.
- Subject: keep only what explains or proves why the audience should care now.
- Ask: choose an action close (book, reply, start, join, approve) or reaction close (worth exploring, want the plan, does this solve it?).
- Memorability: use imagery, simple phrasing, audience-specific detail, and emotion tied to action or inaction.

#### 30-second message formula
Hook: [Earn attention with a relevant question, claim, contrast, or image.]
Point: [State the core idea in plain language.]
Reason: [Give the strongest audience-centered reason to care.]
Proof: [Add one concrete fact, example, outcome, or credibility signal.]
Ask: [Request a specific action or response.]

Compressed version:
Because [audience priority], [offer/idea] helps you [specific result] by [mechanism/proof]. [Ask].

#### Format patterns
Ad/social: hook naming a desire, problem, or contrast → one-sentence promise → proof/mechanism → clear CTA.
Landing hero: Headline = desired outcome or sharp positioning; Subhead = who it is for + what it helps them do + why different; CTA = specific next step; Proof line = metric/customer/use case/guarantee.
Sales email: specific subject → audience-specific observation → value/result → one proof point → simple next step.
Executive memo: decision needed → recommendation → top business impact → essential evidence → owner + timing.
Pitch opening: hook → "Today I want to show you..." → why it matters to audience → simple analogy/approach → early ask.
Voicemail: name → specific reason tied to their interest → one benefit/consequence → specific response by timeframe → contact.

#### Editing passes
1. Objective alignment: remove sentences that do not serve the single objective.
2. Audience relevance: rewrite sender-centered claims into audience-centered outcomes.
3. Hook strength: make the opening specific enough to create recognition, curiosity, urgency, or value.
4. Clarity/compression: cut throat-clearing, internal history, duplicate benefits, abstract modifiers, unsupported superlatives, and long setup.
5. Ask quality: verify the action is explicit, timing is clear, effort is reasonable, and the ask follows from the message.

#### Final quality gate
Before final output, ensure the central point is clear within the first few seconds; the audience can see what is in it for them; hook, proof, and ask point in the same direction; and the copy is concise enough for a distracted person to understand and remember.
""".strip()

    def as_prompt_section(self) -> str:
        return self.prompt_guidance

    def self_check(self, content: str, brief: dict) -> tuple[str, list[str]]:
        failures: list[str] = []
        if len(content) > 3000:
            failures.append(f"exceeds_30_second_message_bounds:{len(content)}>3000")
        if brief.get("product_name") and str(brief["product_name"]).lower() not in content.lower():
            failures.append(f"must_mention_missing:{brief['product_name']}")
        return ("fail" if failures else "pass"), failures
