from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_api_key
from db import get_db
from plugin_loader import get_active_plugin_ids, get_plugin_for_module
from registry import get_module, list_all, list_by_vertical

router = APIRouter(tags=["modules"])


async def _filter_dispatchable_modules(
    modules: list[dict], db: AsyncSession, brand_id: Optional[str] = None
) -> list[dict]:
    # C4: filter using brand-scoped activation when brand_id is provided
    active_plugin_ids = await get_active_plugin_ids(db, brand_id)
    result: list[dict] = []
    for module in modules:
        plugin = get_plugin_for_module(module.get("id", ""))
        if plugin and plugin.manifest.plugin_id not in active_plugin_ids:
            continue
        result.append(module)
    return result


@router.get("/verticals", summary="List registered verticals")
async def get_verticals(
    brand_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    modules = await _filter_dispatchable_modules(list_all(), db, brand_id)
    counts: dict[str, int] = {}
    for module in modules:
        vertical = module.get("vertical") or "unknown"
        counts[vertical] = counts.get(vertical, 0) + 1
    return {"verticals": [{"vertical": v, "module_count": c} for v, c in sorted(counts.items())]}


@router.get("/verticals/{vertical}/modules", summary="List modules in a vertical")
async def get_vertical_modules(
    vertical: str,
    brand_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_api_key),
):
    modules = await _filter_dispatchable_modules(list_by_vertical(vertical), db, brand_id)
    if not modules:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "VERTICAL_NOT_FOUND",
                    "message": f"No modules registered under vertical '{vertical}'",
                    "details": None,
                }
            },
        )
    return {"vertical": vertical, "modules": modules}


@router.get("/modules/{module_id:path}", summary="Get module detail")
async def get_module_detail(module_id: str, _: str = Depends(require_api_key)):
    cls = get_module(module_id)
    if not cls:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {
                    "code": "MODULE_NOT_FOUND",
                    "message": f"Module '{module_id}' is not registered",
                    "details": None,
                }
            },
        )
    return cls().module_info()
