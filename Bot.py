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
YOUR_INFURA_PROJECT_ID = os.getenv("YOUR_INFURA_PROJECT_ID")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)


INFURA_URL = 'https://mainnet.infura.io/v3/'YOUR_INFURA_PROJECT_ID
NFT_CONTRACT_ADDRESS = '0xEb0Ddc0579CF3894C78ae2C4A7d5ec3B36bFa13A'.lower()
ROLE_NAME = 'Verified NFT Holder'

web3 = Web3(Web3.HTTPProvider(INFURA_URL))

# ERC721 ABI snippet for balanceOf
ERC721_ABI = '''
[
    {
        "constant": true,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]
'''

@bot.event
async def on_ready():
    print(f'Bot is online as {bot.user}')

async def check_nft_ownership(address):
    contract = web3.eth.contract(address=NFT_CONTRACT_ADDRESS, abi=ERC721_ABI)
    balance = contract.functions.balanceOf(address).call()
    return balance > 0

@bot.command(name='verify')
async def verify(ctx, eth_address: str):
    server_id = str(ctx.guild.id)
    user_id = str(ctx.author.id)

    # Normalize address
    try:
        checksum_address = web3.toChecksumAddress(eth_address)
    except:
        await ctx.send("Invalid Ethereum address.")
        return

    await ctx.send("Checking NFT ownership, please wait...")

    owns_nft = await bot.loop.run_in_executor(None, check_nft_ownership, checksum_address)
    if not owns_nft:
        await ctx.send("NFT not found for this address.")
        return

    # Assign role
    role = discord.utils.get(ctx.guild.roles, name=ROLE_NAME)
    if not role:
        role = await ctx.guild.create_role(name=ROLE_NAME)
    await ctx.author.add_roles(role)
    await ctx.send(f"{ctx.author.mention} verified and role assigned!")

    # Store in database
    #async with aiosqlite.connect("verified_users.db") as db:
    #    await db.execute(f'''
    #        CREATE TABLE IF NOT EXISTS server_{server_id} (
    #            user_id TEXT PRIMARY KEY,
    #            eth_address TEXT
    #        )
    #    ''')
    #    await db.execute(f'''
    #        INSERT OR REPLACE INTO server_{server_id} (user_id, eth_address)
    #        VALUES (?, ?)
    #    ''', (user_id, checksum_address))
    #    await db.commit()
    #    await ctx.send("Verification saved.")



bot.run(DISCORD_BOT_TOKEN)
