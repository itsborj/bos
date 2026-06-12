import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from db import get_session_factory
from routers.runs import list_runs
from routers.providers import list_providers
from schemas.runs import RunListResponse
from schemas.providers import ProviderInfo

async def test_admin_logic():
    async with get_session_factory()() as db:
        # 1. Test list_runs logic
        print("Testing list_runs logic...")
        try:
            # We can't easily pass 'require_api_key' as a dependency here 
            # because we're calling the function directly.
            # We just pass None or a dummy string for the auth part.
            resp_runs = await list_runs(
                module_id=None, status=None, created_after=None, created_before=None, 
                limit=20, offset=0, db=db, _="mock_key"
            )
            print(f"Run items count: {len(resp_runs.runs)}")
            if resp_runs.runs:
                run = resp_runs.runs[0]
                print(f"Run item keys: {list(run.__dict__.keys())}")
                assert "provider" in run.__dict__
                assert "model" in run.__dict__
                assert "latency_ms" in run.__dict__
                assert "tokens" in run.__dict__
                assert "cost" in run.__dict__
                print("✓ list_runs returns expected fields")
            else:
                print("! /runs returned no data")
        except Exception as e:
            print(f"Error in list_runs: {e}")

        # 2. Test list_providers logic
        print("Testing list_providers logic...")
        try:
            resp_prov = await list_providers(db=db, _="mock_key")
            providers = resp_prov["providers"]
            if providers:
                prov = providers[0]
                # Use .model_dump() because prov is a Pydantic model
                keys = prov.model_dump().keys()
                print(f"Provider item keys: {list(keys)}")
                assert "avg_latency_ms" in keys
                print("✓ list_providers returns expected fields")
            else:
                print("! /providers returned no data")
        except Exception as e:
            print(f"Error in list_providers: {e}")

    print("Logic verification complete.")

if __name__ == "__main__":
    asyncio.run(test_admin_logic())
