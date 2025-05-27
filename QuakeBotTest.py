
import discord
import aiohttp
import asyncio
import datetime
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = 520105533492166656  # Replace with your Discord channel ID
USGS_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"

intents = discord.Intents.default()
client = discord.Client(intents=intents)

last_event_ids = set()

async def fetch_earthquake_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(USGS_FEED_URL) as response:
            if response.status == 200:
                return await response.json()
            else:
                print(f"Failed to fetch USGS data: HTTP {response.status}")
                return None

def is_in_japan(lat, lon):
    return 24.0 <= lat <= 46.0 and 122.0 <= lon <= 153.0

async def check_for_new_earthquakes():
    await client.wait_until_ready()
    channel = client.get_channel(CHANNEL_ID)
    global last_event_ids

    while not client.is_closed():
        data = await fetch_earthquake_data()
        if data:
            new_events = []
            for feature in data["features"]:
                event_id = feature["id"]
                coords = feature["geometry"]["coordinates"]
                lon, lat = coords[0], coords[1]

                if event_id not in last_event_ids and is_in_japan(lat, lon):
                    props = feature["properties"]
                    mag = props["mag"]
                    place = props["place"]
                    time = datetime.datetime.utcfromtimestamp(props["time"] / 1000)
                    url = props["url"]

                    message = (
                        f"🌏 **Earthquake in Japan!**\n"
                        f"**Magnitude**: {mag}\n"
                        f"**Location**: {place}\n"
                        f"**Time (UTC)**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                        f"[More Info]({url})"
                    )
                    new_events.append((event_id, message))

            if new_events:
                for event_id, msg in new_events:
                    await channel.send(msg)
                    last_event_ids.add(event_id)

            if len(last_event_ids) > 100:
                last_event_ids = set(list(last_event_ids)[-100:])

        await asyncio.sleep(60)  # Check every 60 seconds

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

client.loop.create_task(check_for_new_earthquakes())
client.run(TOKEN)