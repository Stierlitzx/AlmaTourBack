import asyncio, asyncpg, os, bcrypt
from dotenv import load_dotenv
load_dotenv()

async def main():
    dsn = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://').split('?')[0]
    conn = await asyncpg.connect(dsn, ssl='require')
    updates = [
        ('admin@almatour.kz', 'admin123'),
        ('guide@almatour.kz', 'guide123'),
        ('tourist@almatour.kz', 'tourist123'),
    ]
    for email, password in updates:
        h = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        await conn.execute('UPDATE users SET password_hash = ' + chr(36) + '1 WHERE email = ' + chr(36) + '2', h, email)
        print('Updated: ' + email)
    await conn.close()

asyncio.run(main())
