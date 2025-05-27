import discord
from discord.ext import commands
from web3 import Web3
import json
import os

# === CONFIGURATION ===
BOT_TOKEN = 'YOUR_DISCORD_BOT_TOKEN'
INFURA_URL = 'https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID'
NFT_CONTRACT_ADDRESS = '0xYourNftContractAddress'
NFT_TOKEN_ID = 1  # You can modify to support multiple IDs
ROLE_NAME = 'NFT Verified'

# === Web3 Setup ===
web3 = Web3(Web3.HTTPProvider(INFURA_URL))

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

# === Initialize bot ===
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

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

    if not Web3.isAddress(eth_address):
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

bot.run(BOT_TOKEN)
