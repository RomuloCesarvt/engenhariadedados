import sys
import os
import asyncio

sys.path.append(r"c:\Users\RomuloMeloMouraLeite\.gemini\antigravity\scratch\LeadSage\backend")

from app.database import init_db, get_db, DBSearchHistory
from sqlalchemy.future import select

async def main():
    print("Testing DB initialization...")
    await init_db()
    print("DB Initialized.")
    
    print("Testing DB insert...")
    async for db in get_db():
        history = DBSearchHistory(
            id="sch_test_123",
            niche="Test",
            location="TestLocation",
            total_leads=5,
            timestamp="2024-01-01 12:00:00",
            leads_preview=["A", "B"]
        )
        db.add(history)
        await db.commit()
        print("Insert successful.")
        break
        
    print("Testing DB select...")
    async for db in get_db():
        result = await db.execute(select(DBSearchHistory))
        items = result.scalars().all()
        print(f"Found {len(items)} items in DB.")
        for item in items:
            print(f"- {item.id}, {item.niche}, {item.location}")
        break

if __name__ == "__main__":
    asyncio.run(main())
