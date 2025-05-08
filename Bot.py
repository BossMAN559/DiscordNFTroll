import discord
from discord.ext import commands
from discord.ext.commands import BucketType
import aiohttp
import aiosqlite
import re
import os
from dotenv import load_dotenv

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)






bot.run(DISCORD_BOT_TOKEN)
