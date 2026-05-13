from fastapi import APIRouter, Depends, HTTPException

from auth import require_api_key
from registry import get_module, list_all, list_by_vertical, list_verticals

router = APIRouter(tags=["modules"])


@router.get("/verticals", summary="List registered verticals")
async def get_verticals(_: str = Depends(require_api_key)):
    return {"verticals": list_verticals()}


@router.get("/verticals/{vertical}/modules", summary="List modules in a vertical")
async def get_vertical_modules(vertical: str, _: str = Depends(require_api_key)):
    modules = list_by_vertical(vertical)
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
