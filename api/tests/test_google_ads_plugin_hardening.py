from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "plugins/google-ads/capabilities/marketing/channel/google_ads/performance/read/module.py"
)


def _module_class():
    spec = importlib.util.spec_from_file_location("google_ads_read_module", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.GoogleAdsReadOnlyDataPullModule


def test_google_ads_customer_id_normalization_handles_common_copy_paste_shapes():
    module = _module_class()()

    assert module._customer_id("123-456-7890") == "1234567890"
    assert module._customer_id('"123-456-7890"') == "1234567890"
    assert module._customer_id("customers/123-456-7890") == "1234567890"
    assert module._customer_id("987318670") == "0987318670"
    assert module._customer_id(None) == ""


def test_google_ads_api_version_normalization():
    module = _module_class()()

    assert module._api_version("21") == "v21"
    assert module._api_version("v21") == "v21"
    assert module._api_version("") == "v21"
