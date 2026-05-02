import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()

async def main():
    dsn = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://').split('?')[0]
    conn = await asyncpg.connect(dsn, ssl='require')
    try:
        await conn.execute("ALTER TABLE tours ADD COLUMN image_url TEXT")
        print('Added image_url column')
    except Exception as e:
        print('image_url already exists:', e)
    try:
        await conn.execute("ALTER TABLE tours ADD COLUMN badge VARCHAR(50) DEFAULT 'Nature'")
        print('Added badge column')
    except Exception as e:
        print('badge already exists:', e)
    await conn.close()

asyncio.run(main())
