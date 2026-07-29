from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
API_PATH = ROOT / "api"
if str(API_PATH) not in sys.path:
    sys.path.insert(0, str(API_PATH))

from routers.onboarding import _build_client_readiness_snapshot


def test_client_readiness_snapshot_distinguishes_drive_reauth_and_backend_blockers() -> None:
    snapshot = _build_client_readiness_snapshot(
        brand_profile_configured=True,
        campaign_brand_kit_approved=True,
        drive_connection_status="needs_reauth",
        drive_root_name="Brand Kit",
        brand_mark_configured=True,
        publish_channels=["facebook"],
        live_campaign_present=False,
        capability_ready_count=2,
        capability_total_count=5,
        installed_plugin_count=3,
        active_plugin_count=3,
    )

    assert snapshot.drive.ok is False
    assert snapshot.drive.label == "Reconnect required"
    assert snapshot.blockers[0] == "Reconnect Drive"
    assert snapshot.blockers[1] == "Create live campaign"
    assert snapshot.blockers[2] == "Fix capability setup"
    assert snapshot.next_action.key == "reconnect_drive"
    assert snapshot.capabilities.label == "2/5 ready"


def test_client_readiness_snapshot_uses_backend_profile_truth_not_partial_brand_fields() -> None:
    snapshot = _build_client_readiness_snapshot(
        brand_profile_configured=False,
        campaign_brand_kit_approved=False,
        drive_connection_status=None,
        drive_root_name=None,
        brand_mark_configured=False,
        publish_channels=[],
        live_campaign_present=False,
        capability_ready_count=0,
        capability_total_count=0,
        installed_plugin_count=0,
        active_plugin_count=0,
    )

    assert snapshot.brief.ok is False
    assert snapshot.brief.label == "Missing"
    assert snapshot.brand_kit.label == "Missing"
    assert snapshot.blockers[:5] == [
        "Import brand brief",
        "Approve brand kit",
        "Connect Drive",
        "Connect publish channel",
        "Create live campaign",
    ]
    assert snapshot.blockers[-1] == "Install capabilities"
    assert snapshot.next_action.key == "import_brief"
