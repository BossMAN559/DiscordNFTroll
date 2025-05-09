import discord
from discord.ext import commands
from discord.ext.commands import BucketType
from web3 import Web3
import aiohttp
import json
import aiosqlite
import re
import os
from dotenv import load_dotenv

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
YOUR_INFURA_PROJECT_ID = os.getenv("YOUR_INFURA_PROJECT_ID")
NFT_TOKEN_ID = 1

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

NFT_CONTRACT_ADDRESS = '0xEb0Ddc0579CF3894C78ae2C4A7d5ec3B36bFa13A'.lower()
ROLE_NAME = 'Verified NFT Holder'

# === Web3 Setup ===
web3 = Web3(Web3.HTTPProvider(YOUR_INFURA_PROJECT_ID))

# === ERC721 ABI Snippet ===
ERC721_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_tokenId", "type": "uint256"}
        ],
        "name": "ownerOf",
        "outputs": [{"name": "owner", "type": "address"}],
        "type": "function",
    }
]

# === Helper Functions ===

def load_data(server_name):
    filename = f"{server_name}_nft_users.json"
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def save_data(server_name, data):
    filename = f"{server_name}_nft_users.json"
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

def is_nft_owner(address):
    contract = web3.eth.contract(address=web3.toChecksumAddress(NFT_CONTRACT_ADDRESS), abi=ERC721_ABI)
    try:
        owner = contract.functions.ownerOf(NFT_TOKEN_ID).call()
        return Web3.toChecksumAddress(address) == Web3.toChecksumAddress(owner)
    except Exception as e:
        print(f"Error checking NFT ownership: {e}")
        return False

# === Bot Events and Commands ===

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.command()
async def verify(ctx, eth_address: str):
    server_name = ctx.guild.name.replace(" ", "_")
    user = ctx.author

    if not web3.utils.isAddress(eth_address):
        await ctx.send("Invalid Ethereum address.")
        return

    await ctx.send("Checking NFT ownership...")

    if is_nft_owner(eth_address):
        role = discord.utils.get(ctx.guild.roles, name=ROLE_NAME)
        if not role:
            role = await ctx.guild.create_role(name=ROLE_NAME)

        await user.add_roles(role)
        await ctx.send(f"Verification complete! Role '{ROLE_NAME}' assigned.")

        data = load_data(server_name)
        data[str(user.id)] = eth_address
        save_data(server_name, data)
    else:
        await ctx.send("NFT ownership not verified. Please ensure you own the correct NFT.")


bot.run(DISCORD_BOT_TOKEN)
