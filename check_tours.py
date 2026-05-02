import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()

async def main():
    dsn = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://').split('?')[0]
    conn = await asyncpg.connect(dsn, ssl='require')
    count = await conn.fetchval('SELECT COUNT(*) FROM tours')
    print('Tours in DB:', count)
    await conn.close()

asyncio.run(main())
