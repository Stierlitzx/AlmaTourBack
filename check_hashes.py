import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()

async def main():
    dsn = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://').split('?')[0]
    conn = await asyncpg.connect(dsn, ssl='require')
    rows = await conn.fetch('SELECT email, password_hash FROM users')
    for r in rows:
        print(r['email'], '|', r['password_hash'][:30], '...')
    await conn.close()

asyncio.run(main())
