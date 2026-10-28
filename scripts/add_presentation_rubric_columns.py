import asyncio
from sqlalchemy import text
from services.api.core.db import engine

async def main():
    async with engine.begin() as conn:
        print("Adding columns to presentations...")
        await conn.execute(text("ALTER TABLE presentations ADD COLUMN IF NOT EXISTS problem_statement TEXT;"))
        print("Adding columns to presentation_scores...")
        await conn.execute(text("ALTER TABLE presentation_scores ADD COLUMN IF NOT EXISTS problem_statement TEXT;"))
        await conn.execute(text("ALTER TABLE presentation_scores ADD COLUMN IF NOT EXISTS requirement_coverage JSONB;"))
        await conn.execute(text("ALTER TABLE presentation_scores ADD COLUMN IF NOT EXISTS rubric_breakdown JSONB;"))
        print("Successfully updated database schema.")

if __name__ == "__main__":
    asyncio.run(main())
