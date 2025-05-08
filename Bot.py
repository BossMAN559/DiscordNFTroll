import discord
from discord.ext import commands
import aiohttp
import aiosqlite
import re

DISCORD_BOT_TOKEN = 'YOUR_DISCORD_BOT_TOKEN'

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Helper: sanitize for SQLite table names
def sanitize_server_name(name):
    return re.sub(r'\W+', '_', name.strip().lower())

# Fetch server-specific config
async def get_server_config(server_name):
    async with aiosqlite.connect("verified_users.db") as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS server_settings (
                server_name TEXT PRIMARY KEY,
                alchemy_api_key TEXT,
                nft_contract TEXT,
                role_name TEXT
            )
        ''')
        cursor = await db.execute('SELECT alchemy_api_key, nft_contract, role_name FROM server_settings WHERE server_name = ?', (server_name,))
        row = await cursor.fetchone()
        return row if row else None

# Store server-specific config
async def set_server_config(server_name, alchemy_key, nft_contract, role_name):
    async with aiosqlite.connect("verified_users.db") as db:
        await db.execute('''
            INSERT OR REPLACE INTO server_settings (server_name, alchemy_api_key, nft_contract, role_name)
            VALUES (?, ?, ?, ?)
        ''', (server_name, alchemy_key, nft_contract.lower(), role_name))
        await db.commit()

# Check NFT ownership via Alchemy
async def owns_nft(address, alchemy_key, contract_address):
    url = f"https://eth-mainnet.g.alchemy.com/nft/v2/{alchemy_key}/getNFTs"
    params = {
        "owner": address,
        "contractAddresses[]": contract_address
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return False
            data = await resp.json()
            return data.get("ownedNfts", []) != []

@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user}')

# ✅ Admin command to set NFT config
@bot.command(name="setnftconfig")
@commands.has_permissions(administrator=True)
async def setnftconfig(ctx, alchemy_key: str, nft_contract: str, *, role_name: str):
    server_name = sanitize_server_name(ctx.guild.name)
    await set_server_config(server_name, alchemy_key, nft_contract, role_name)
    await ctx.send("NFT verification config saved for this server.")

# ✅ Verify command for users
@bot.command(name="verify")
async def verify(ctx, eth_address: str):
    server_name = sanitize_server_name(ctx.guild.name)
    user_id = str(ctx.author.id)

    config = await get_server_config(server_name)
    if not config:
        await ctx.send("Server NFT config not set. Ask an admin to run `!setnftconfig`.")
        return

    alchemy_key, nft_contract, role_name = config

    if not eth_address.startswith('0x') or len(eth_address) != 42:
        await ctx.send("Invalid Ethereum address.")
        return

    await ctx.send("Verifying NFT ownership...")

    if not await owns_nft(eth_address, alchemy_key, nft_contract):
        await ctx.send("No matching NFT found for this address.")
        return

    # Assign role
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if not role:
        role = await ctx.guild.create_role(name=role_name)
    await ctx.author.add_roles(role)
    await ctx.send(f"{ctx.author.mention} verified and role '{role_name}' assigned!")

    # Store verified user
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

# Handle permission errors
@setnftconfig.error
async def setnftconfig_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You must be an administrator to use this command.")

bot.run(DISCORD_BOT_TOKEN)
