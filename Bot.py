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
@commands.cooldown(rate=1, per=60.0, type=BucketType.user)  # 1 use per 60 seconds per user
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


# ✅ Admin command to list all verified users
@bot.command(name="listverified")
@commands.cooldown(rate=1, per=30.0, type=BucketType.guild)  # 1 per 30 sec per guild
@commands.has_permissions(administrator=True)
async def list_verified(ctx):
    server_name = sanitize_server_name(ctx.guild.name)

    async with aiosqlite.connect("verified_users.db") as db:
        await db.execute(f'''
            CREATE TABLE IF NOT EXISTS server_{server_name} (
                user_id TEXT PRIMARY KEY,
                eth_address TEXT
            )
        ''')
        cursor = await db.execute(f'''
            SELECT user_id, eth_address FROM server_{server_name}
        ''')
        rows = await cursor.fetchall()

    if not rows:
        await ctx.send("No users have been verified on this server.")
        return

    message = "**Verified Users:**\n"
    for user_id, address in rows:
        member = ctx.guild.get_member(int(user_id))
        if member:
            message += f"- {member.mention} — `{address}`\n"
        else:
            message += f"- (Left) <@{user_id}> — `{address}`\n"

    await ctx.send(message)

# ✅ Admin command to unverify a user
@bot.command(name="unverify")
@commands.has_permissions(administrator=True)
async def unverify(ctx, member: discord.Member):
    server_name = sanitize_server_name(ctx.guild.name)
    config = await get_server_config(server_name)
    if not config:
        await ctx.send("Server NFT config not set.")
        return

    _, _, role_name = config

    # Remove role
    role = discord.utils.get(ctx.guild.roles, name=role_name)
    if role in member.roles:
        await member.remove_roles(role)

    # Remove from DB
    async with aiosqlite.connect("verified_users.db") as db:
        await db.execute(f'''
            DELETE FROM server_{server_name} WHERE user_id = ?
        ''', (str(member.id),))
        await db.commit()

    await ctx.send(f"{member.mention} has been unverified and the role removed.")

# Error handler for permission issues
@list_verified.error
@unverify.error
async def admin_cmd_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You must be an administrator to use this command.")

@verify.error
async def verify_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"You're doing that too much! Try again in {int(error.retry_after)} seconds.")
    else:
        raise error

@list_verified.error
async def list_verified_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Please wait {int(error.retry_after)} seconds before using this command again.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You must be an administrator to use this command.")

bot.run(DISCORD_BOT_TOKEN)
