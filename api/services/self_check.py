"""Self-check repair guidance extracted from routers/runs.py."""


def self_check_repair_guidance(failures: list[str]) -> str:
    """Build a human-readable repair instruction list from self-check failure codes."""
    guidance: list[str] = []
    for failure in failures:
        if failure == "unsupported_do_now_channel_without_context:email_list":
            guidance.append(
                "Move Email marketing/newsletter/email nurture out of Do now and into Hold "
                "unless an owned list, CRM, subscribers, opt-ins, or lead database is explicitly loaded."
            )
        elif failure.startswith("unsupported_do_now_channel_without_context:"):
            channel = failure.rsplit(":", 1)[-1].replace("_", " ")
            guidance.append(
                f"Remove {channel} from Do now unless the loaded context explicitly proves "
                f"the prerequisite asset exists; put it in Hold or Avoid with an unlock condition."
            )
        elif failure == "invalid_motion_taxonomy":
            guidance.append(
                "Use exactly one of these motion names: founder-led, product-led, "
                "sales-led, content-led, partner-led, community-led."
            )
        elif failure == "invented_numeric_target_or_proof":
            guidance.append(
                "Remove fabricated numbers, budgets, percentages, lead counts, revenue targets, "
                "and proof thresholds unless supplied in the brief."
            )
        elif failure == "too_many_do_now_channels":
            guidance.append("Limit Do now to at most three channels.")
    return "\n".join(f"- {item}" for item in guidance)
