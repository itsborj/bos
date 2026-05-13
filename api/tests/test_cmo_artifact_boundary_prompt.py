from pathlib import Path


PROMPT_PATH = Path(__file__).resolve().parents[1] / "capabilities/workspace/cmo_context/SYSTEM_PROMPT.md"


def test_prompt_forbids_inline_broad_sample_outputs():
    prompt = PROMPT_PATH.read_text()

    assert "let me see samples" in prompt
    assert "must never be answered with inline platform-native content" in prompt
    assert "If the request is broad or ambiguous, ask which reviewable artifact" in prompt
    assert "Do not write Subject/Body" in prompt
    assert "Hidden directive after the reply: none" in prompt
