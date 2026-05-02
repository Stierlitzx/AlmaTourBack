import asyncio, asyncpg, os
from dotenv import load_dotenv
load_dotenv()

TOURS = [
    ("Kolsay Lake", "Discover the breathtaking beauty of the Kolsai Lakes, known as the Pearls of the Northern Tien Shan. Enjoy crystal-clear waters, lush forests, and peaceful mountain landscapes.", 25000, 10, 43.0113, 78.4700, "Kolsay Lakes, Almaty Region", "2026-07-15", 9, "Nature", "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=800&q=80"),
    ("Shymbulak Resort", "Experience the stunning alpine scenery of Shymbulak Mountain Resort, nestled at 2,200 meters in the Zailiysky Alatau range, just 25 km from central Almaty.", 30000, 8, 43.1393, 77.0785, "Shymbulak, Almaty", "2026-07-20", 4, "Nature", "https://images.unsplash.com/photo-1518091043644-c1d4457512c6?w=800&q=80"),
    ("Charyn Canyon", "Explore the magnificent Charyn Canyon, often called the Grand Canyon little brother. Marvel at ancient red rock formations carved by the Charyn River over millions of years.", 20000, 12, 43.3503, 79.0700, "Charyn Canyon, Almaty Region", "2026-08-05", 8, "Adventure", "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=800&q=80"),
    ("Kaindy Lake", "Visit the surreal Kaindy Lake, formed by a 1911 earthquake, where submerged birch trees rise eerily from its turquoise waters.", 20000, 14, 42.9917, 78.4600, "Kaindy Lake, Almaty Region", "2026-08-10", 9, "Nature", "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?w=800&q=80"),
    ("Medeu Ice Rink", "Skate at the world highest outdoor ice rink, Medeu, set at 1,691 meters above sea level with spectacular mountain views all around.", 25000, 8, 43.1560, 77.0572, "Medeu, Almaty", "2026-08-15", 6, "Adventure", "https://images.unsplash.com/photo-1518091043644-c1d4457512c6?w=800&q=80"),
    ("Kok-Tobe Hill", "Take in panoramic views of Almaty from Kok-Tobe Hill, reached by a scenic cable car ride. Enjoy attractions, the Beatles statue, and sweeping city vistas from 1,100 meters.", 18000, 14, 43.2335, 76.9720, "Kok-Tobe, Almaty", "2026-08-20", 4, "City tours", "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=800&q=80"),
    ("Ayusai Waterfall", "Discover the hidden Ayusai Waterfall nestled in the gorges of Ile-Alatau National Park. A refreshing half-day escape with lush greenery, cool mist and peaceful forest trails.", 15000, 12, 43.1700, 77.0100, "Ile-Alatau National Park, Almaty", "2026-08-25", 5, "Nature", "https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=800&q=80"),
    ("Kok Zhailau Plateau", "Hike up to the iconic Kok Zhailau plateau for sweeping panoramic views of Almaty and the surrounding Tian Shan peaks. One of the most beloved trails in Kazakhstan.", 18000, 14, 43.1800, 77.0300, "Kok Zhailau, Almaty", "2026-09-01", 6, "Nature", "https://images.unsplash.com/photo-1501854140801-50d01698950b?w=800&q=80"),
    ("Alma-Arasan Gorge", "Stroll through the tranquil Alma-Arasan gorge, home to a natural hot spring resort, pine forests, and a gently flowing mountain river.", 12000, 16, 43.1650, 76.9800, "Alma-Arasan, Almaty", "2026-09-05", 4, "Nature", "https://images.unsplash.com/photo-1500534314209-a25ddb2bd429?w=800&q=80"),
    ("Terrenkur Trail", "Walk the legendary Terrenkur, a scenic therapeutic mountain path running from Medeu to Shymbulak. Enjoy fresh alpine air, pine forests, and stunning city views below.", 10000, 20, 43.1480, 77.0650, "Medeu, Almaty", "2026-09-10", 3, "City tours", "https://images.unsplash.com/photo-1518098268026-4e89f1a2cd8e?w=800&q=80"),
    ("Assy Plateau", "Journey to the vast Assy Plateau at 2,700 meters, a rolling highland steppe used by nomads for centuries. Experience real Kazakh pastoral life, yurts, horses and boundless sky.", 28000, 8, 43.2500, 77.8000, "Assy Plateau, Almaty Region", "2026-09-15", 10, "Adventure", "https://images.unsplash.com/photo-1505118380757-91f5f5632de0?w=800&q=80"),
    ("Turgen Waterfalls", "Explore the stunning Turgen Gorge with its series of seven waterfalls, the famous bear cave, and ancient petroglyphs.", 22000, 12, 43.2800, 77.6500, "Turgen Gorge, Almaty Region", "2026-09-20", 8, "Nature", "https://images.unsplash.com/photo-1434725039720-aaad6dd32dfe?w=800&q=80"),
    ("Bartogay Reservoir", "Visit the turquoise waters of Bartogay Reservoir set against a backdrop of snow-capped peaks. A peaceful destination for photography, picnics and mountain lake scenery.", 20000, 14, 43.4800, 77.9500, "Bartogay, Almaty Region", "2026-09-25", 9, "Nature", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=800&q=80"),
    ("Issyk Lake", "Visit Issyk Lake, a beautiful glacial lake in the Tian Shan foothills famous for its emerald water and the legendary Golden Man archaeological museum nearby.", 17000, 12, 43.3500, 77.4700, "Issyk, Almaty Region", "2026-10-01", 7, "Nature", "https://images.unsplash.com/photo-1478827217976-7214a0556393?w=800&q=80"),
    ("Panfilov Park", "Explore Almaty most beloved city park, home to the magnificent Zenkov Cathedral, the Memorial of Glory, and a peaceful green oasis in the heart of the city.", 8000, 20, 43.2551, 76.9440, "Panfilov Park, Almaty", "2026-10-05", 3, "City tours", "https://images.unsplash.com/photo-1512453979798-5ea266f8880c?w=800&q=80"),
]

async def main():
    dsn = os.environ['DATABASE_URL'].replace('postgresql+asyncpg://', 'postgresql://').split('?')[0]
    conn = await asyncpg.connect(dsn, ssl='require')

    # Check h3 version
    import h3
    print('h3 version:', h3.__version__)

    # Try both old and new h3 API
    def get_h3(lat, lng, res):
        try:
            return h3.latlng_to_cell(lat, lng, res)  # h3 4.x
        except AttributeError:
            return h3.geo_to_h3(lat, lng, res)       # h3 3.x

    await conn.execute('DELETE FROM tours')
    print('Deleted existing tours')

    guide_id = 2

    for t in TOURS:
        title, desc, price, capacity, lat, lng, location, date, duration, badge, img = t
        h3_index = get_h3(lat, lng, 8)
        h3_region = get_h3(lat, lng, 5)
        await conn.execute('''
            INSERT INTO tours (title, description, guide_id, price, capacity, seats_available,
                lat, lng, h3_index, h3_region, location_name, schedule_date, duration_hours,
                status, image_url, badge)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
        ''', title, desc, guide_id, float(price), capacity, capacity,
            lat, lng, h3_index, h3_region, location, date, float(duration),
            'active', img, badge)
        print(f'Added: {title}')

    await conn.close()
    print('Done! All 15 tours seeded.')

asyncio.run(main())