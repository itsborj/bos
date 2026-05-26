from db import get_db
from models.workspace import Brand
from sqlalchemy import select
import asyncio

async def main():
    async for db in get_db():
        res = await db.execute(select(Brand).limit(1))
        brand = res.scalar_one_or_none()
        if brand:
            print(brand.id)
        else:
            print("No brand found")

if __name__ == '__main__':
    asyncio.run(main())
