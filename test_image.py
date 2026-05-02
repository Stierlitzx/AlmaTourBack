import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()

IMAGES = {
    'Kolsay Lake':         'https://res.cloudinary.com/dxrk1grhm/image/upload/v1777726822/kolsay_rct78o.jpg',
    'Shymbulak Resort':    'https://res.cloudinary.com/dxrk1grhm/image/upload/v1777726820/shymb_l6hu9x.jpg',
    'Charyn Canyon':       'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=800&q=80',
    'Kaindy Lake':         'https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=800&q=80',
    'Medeu Ice Rink':      'https://res.cloudinary.com/dxrk1grhm/image/upload/v1777726822/medeu_qc7ys7.jpg',
    'Kok-Tobe Hill':       'https://res.cloudinary.com/dxrk1grhm/image/upload/v1777726822/kolsay_rct78o.jpg',
    'Ayusai Waterfall':    'https://res.cloudinary.com/dxrk1grhm/image/upload/v1777726367/ayusai_fqjwan.jpg',
    'Kok Zhailau Plateau': 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800&q=80',
    'Alma-Arasan Gorge':   'https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?w=800&q=80',
    'Terrenkur Trail':     'https://images.unsplash.com/photo-1518098268026-4e89f1a2cd8e?w=800&q=80',
    'Assy Plateau':        'https://images.unsplash.com/photo-1505118380757-91f5f5632de0?w=800&q=80',
    'Turgen Waterfalls':   'https://images.unsplash.com/photo-1434725039720-aaad6dd32dfe?w=800&q=80',
    'Bartogay Reservoir':  'https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80',
    'Issyk Lake':          'https://images.unsplash.com/photo-1478827217976-7214a0556393?w=800&q=80',
    'Panfilov Park':       'https://res.cloudinary.com/dxrk1grhm/image/upload/v1777726821/panfilov-park_skbo1w.jpg',
}

async def main():
    dsn = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://').split('?')[0]
    conn = await asyncpg.connect(dsn, ssl='require')
    for title, url in IMAGES.items():
        await conn.execute('UPDATE tours SET image_url = $1 WHERE title = $2', url, title)
        print('Updated:', title)
    await conn.close()
    print('Done!')

asyncio.run(main())