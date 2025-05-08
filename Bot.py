import discord
from discord.ext import commands
import aiohttp
import aiosqlite
import re

DISCORD_BOT_TOKEN = 'YOUR_DISCORD_BOT_TOKEN'
ALCHEMY_API_KEY = 'YOUR_ALCHEMY_API_KEY'
NFT_CONTRACT_ADDRESS = '0xYourNftContractAddress'.lower()
ROLE_NAME = 'Verified NFT Holder'

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Helper: Sanitize server name for SQLite table use
def sanitize_server_name(name):
    return re.sub(r'\W+', '_', name.strip().lower())

async def owns_nft(address):
    url = f"https://eth-mainnet.g.alchemy.com/nft/v2/{ALCHEMY_API_KEY}/getNFTs"
    params = {
        "owner": address,
        "contractAddresses[]": NFT_CONTRACT_ADDRESS
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return False
            data = await resp.json()
            return data.get("ownedNfts", []) != []

@bot.event
async def on_ready():
    print(f'Bot is ready. Logged in as {bot.user}')

@bot.command(name="verify")
async def verify(ctx, eth_address: str):
    server_name = sanitize_server_name(ctx.guild.name)
    user_id = str(ctx.author.id)

    # Normalize ETH address
    if not eth_address.startswith('0x') or len(eth_address) != 42:
        await ctx.send("Invalid Ethereum address.")
        return

    await ctx.send("Verifying NFT ownership...")

    if not await owns_nft(eth_address):
        await ctx.send("No matching NFT found for this address.")
        return

    # Assign role
    role = discord.utils.get(ctx.guild.roles, name=ROLE_NAME)
    if not role:
        role = await ctx.guild.create_role(name=ROLE_NAME)
    await ctx.author.add_roles(role)
    await ctx.send(f"{ctx.author.mention} verified and role '{ROLE_NAME}' assigned!")

    # Store in SQLite using server name
    async with aiosqlite.connect("verified_users.db") as db:
        await db.execute(f'''
            CREATE TABLE IF NOT EXISTS server_{server_name} (
                user_id TEXT PRIMARY KEY,
                eth_address TEXT
            )
        ''')
        await db.execute(f'''
            INSERT OR REPLACE INTO server_{server_name} (user_id, eth_address)
            VALUES (?, ?)
        ''', (user_id, eth_address))
        await db.commit()
        await ctx.send("Verification data saved.")


bot.run(DISCORD_BOT_TOKEN)
