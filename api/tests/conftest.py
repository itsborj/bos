from __future__ import annotations

import os

# Load bundled api/plugins/ examples during the test suite so routing, manifest,
# and smoke tests can assert against SDK example capabilities without requiring
# all of them to be copied to ~/bos-plugins/.  External plugins (if present in
# EXTERNAL_PLUGINS_DIR) still take precedence when IDs overlap — the loader
# skips internal plugins that are already registered from an external source.
os.environ["KLAROHA_LOAD_INTERNAL_PLUGINS"] = "true"
