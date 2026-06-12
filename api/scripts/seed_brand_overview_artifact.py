#!/usr/bin/env python3
"""Seed script: create a brand_overview artifact for every brand in the workspace.

Run inside the API container:
  docker compose exec api python scripts/seed_brand_overview_artifact.py

Inserts Run + RunResult + RunTrace rows. Safe to re-run — uses a fixed
deterministic module_id so existing rows are detected and skipped.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import asyncpg

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://bos:bos@db:5432/bos")
# asyncpg uses postgresql:// not postgresql+asyncpg://
ASYNCPG_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql://", "postgresql://")

MODULE_ID = "workspace.brand.overview"


def _parse_json(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


def _build_brand_block(
    brand: dict,
    products: list[dict],
    audiences: list[dict],
    campaigns: list[dict],
    connections: list[dict],
    recent_run_count: int,
    recent_by_module: list[dict],
) -> dict:
    identity_raw = brand.get("brand_json") or {}
    social_handles: dict = brand.get("social_handles") or {}

    connected = [
        {
            "platform": c["platform"],
            "account": c.get("page_name") or c.get("page_id") or "",
            "status": c.get("status", "connected"),
        }
        for c in connections
        if c.get("brand_id") == brand["id"]
    ]
    connected_platform_names = {c["platform"] for c in connected}
    unconnected_handles = [p for p in social_handles if p not in connected_platform_names]

    active_campaigns = [c for c in campaigns if c.get("status") == "active"]
    draft_campaigns = [c for c in campaigns if c.get("status") == "draft"]

    readiness_gaps = []
    if not products:
        readiness_gaps.append("product catalog")
    if not audiences:
        readiness_gaps.append("audience profiles")
    if not brand.get("voice"):
        readiness_gaps.append("brand voice")
    if not brand.get("tone"):
        readiness_gaps.append("brand tone")
    if not social_handles:
        readiness_gaps.append("social handles")

    # readiness_gaps is returned in the artifact; profile_complete was a dead alias.

    return {
        "type": "brand_overview",
        "artifact_type": "intelligence_artifact",
        "title": f"Brand Overview — {brand['name']}",
        "status": "pending_review",
        "brand": {
            "id": brand["id"],
            "name": brand["name"],
            "domain": brand.get("domain") or None,
            "website_url": brand.get("website_url") or None,
        },
        "identity": {
            "voice": brand.get("voice") or identity_raw.get("voice") or None,
            "tone": brand.get("tone") or identity_raw.get("tone") or None,
            "values": brand.get("values") or identity_raw.get("values") or [],
            "tagline": identity_raw.get("tagline") or None,
            "positioning": identity_raw.get("positioning") or None,
        },
        "digital_presence": {
            "handles": social_handles,
            "connected_channels": connected,
            "unconnected_handles": unconnected_handles,
        },
        "products": [
            {
                "id": p["id"],
                "name": p["name"],
                "tagline": p.get("tagline") or None,
                "benefits": _parse_json(p.get("benefits_json")).get("items") or [],
            }
            for p in products
        ],
        "audiences": [
            {
                "id": a["id"],
                "name": a["name"],
                "segment": _parse_json(a.get("segment_json")),
            }
            for a in audiences
        ],
        "campaigns": {
            "active": [{"id": c["id"], "name": c["name"]} for c in active_campaigns],
            "draft": [{"id": c["id"], "name": c["name"]} for c in draft_campaigns],
            "total": len(campaigns),
        },
        "recent_runs": {
            "total_30d": recent_run_count,
            "by_module": recent_by_module,
        },
        "pm_config": brand.get("pm_config") or {},
        "readiness": {
            "brand_profile_complete": len(readiness_gaps) == 0,
            "has_products": len(products) > 0,
            "has_audiences": len(audiences) > 0,
            "connected_channels_count": len(connected),
            "missing_capabilities": readiness_gaps,
        },
        "allowed_actions": ["revise", "dismiss"],
        "changed_resources": [],
        "risk_level": "read_only",
    }


async def main() -> None:
    conn = await asyncpg.connect(ASYNCPG_URL)

    ws_row = await conn.fetchrow("SELECT id FROM workspaces LIMIT 1")
    if not ws_row:
        print("ERROR: no workspace found")
        sys.exit(1)
    ws_id = str(ws_row["id"])
    print(f"Workspace: {ws_id}")

    brands = [dict(r) for r in await conn.fetch(
        "SELECT id::text, workspace_id::text, name, brand_json FROM brands WHERE workspace_id = $1 ORDER BY name",
        ws_row["id"],
    )]
    # Unpack brand_json into top-level keys for convenience
    for b in brands:
        raw = b.get("brand_json") or {}
        bj = json.loads(raw) if isinstance(raw, str) else (raw or {})
        b["brand_json"] = bj
        for field in ("voice", "tone", "values", "domain", "website_url", "social_handles", "pm_config"):
            b[field] = bj.get(field)
    print(f"Brands found: {len(brands)}")

    products_all = [dict(r) for r in await conn.fetch(
        "SELECT id::text, brand_id::text, name, tagline, benefits_json FROM products WHERE workspace_id = $1",
        ws_row["id"],
    )]
    audiences_all = [dict(r) for r in await conn.fetch(
        "SELECT id::text, brand_id::text, name, segment_json FROM audiences WHERE workspace_id = $1",
        ws_row["id"],
    )]
    campaigns_all = [dict(r) for r in await conn.fetch(
        "SELECT id::text, brand_id::text, name, status FROM campaigns WHERE workspace_id = $1",
        ws_row["id"],
    )]
    connections_all = [dict(r) for r in await conn.fetch(
        "SELECT id::text, brand_id::text, platform, page_id, page_name, page_handle, status FROM social_connections WHERE brand_id IN (SELECT id FROM brands WHERE workspace_id = $1)",
        ws_row["id"],
    )]

    for brand in brands:
        brand_id = brand["id"]
        brand_uuid = uuid.UUID(brand_id)

        products = [p for p in products_all if p.get("brand_id") == brand_id]
        audiences = [a for a in audiences_all if a.get("brand_id") == brand_id]
        campaigns = [c for c in campaigns_all if c.get("brand_id") == brand_id]

        run_count = await conn.fetchval(
            "SELECT COUNT(*) FROM runs WHERE brand_id = $1 AND created_at >= NOW() - INTERVAL '30 days'",
            brand_uuid,
        )
        by_module_rows = await conn.fetch(
            "SELECT module_id, COUNT(*) as cnt FROM runs WHERE brand_id = $1 AND created_at >= NOW() - INTERVAL '30 days' GROUP BY module_id ORDER BY cnt DESC LIMIT 5",
            brand_uuid,
        )
        recent_by_module = [{"module_id": r["module_id"], "count": r["cnt"]} for r in by_module_rows]

        block = _build_brand_block(
            brand=brand,
            products=products,
            audiences=audiences,
            campaigns=campaigns,
            connections=connections_all,
            recent_run_count=int(run_count or 0),
            recent_by_module=recent_by_module,
        )

        run_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        await conn.execute(
            """
            INSERT INTO runs (id, workspace_id, brand_id, module_id, status, approval_status, created_at, updated_at)
            VALUES ($1, $2, $3, $4, 'success', 'pending', $5, $5)
            """,
            run_id, uuid.UUID(ws_id), brand_uuid, MODULE_ID, now,
        )

        await conn.execute(
            """
            INSERT INTO run_results (id, run_id, content, self_check_verdict, created_at)
            VALUES ($1, $2, $3, 'pass', $4)
            """,
            uuid.uuid4(), run_id, f"Brand overview for {brand['name']}.", now,
        )

        await conn.execute(
            """
            INSERT INTO run_traces (id, run_id, routing_json, lineage_json, created_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            uuid.uuid4(), run_id,
            json.dumps({"capability": MODULE_ID, "policy": "read_only", "candidates_considered": 0, "candidates_filtered": 0, "routing_reason": "brand_overview_seed"}),
            json.dumps({"block": block, "self_check": "pass", "platform": "brand"}),
            now,
        )

        print(f"  Created artifact run_id={run_id} for brand={brand['name']}")
        print(f"  Block preview: type={block['type']}, channels={len(block['digital_presence']['connected_channels'])}, products={len(block['products'])}")

    await conn.close()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
