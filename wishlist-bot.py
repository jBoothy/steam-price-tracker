import os
import discord
import requests
from discord.ext import commands
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Discord Config
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

# Discord Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Add Game Command
async def fetch_steam_id(game_name):
    """Search for a game's Steam ID using the Steam Store API."""
    url = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
    response = requests.get(url)

    if response.status_code != 200:
        print(f"❌ Failed to fetch Steam app list: {response.status_code}")
        return None

    # Search for the game in the Steam data
    app_list = response.json()["applist"]["apps"]
    for app in app_list:
        if game_name.lower() in app["name"].lower():
            return str(app["appid"])  # Return the matching Steam ID as a string

    return None  # No match found

@bot.command(name='add')
async def add_game(ctx, *, game_name: str):
    """Add a game to the wishlist with the correct Steam ID."""
    existing_game = (
        supabase.table("wishlist")
        .select("game_name")
        .eq("game_name", game_name)
        .execute()
    )

    if existing_game.data:
        await ctx.send(f"❌ **{game_name}** is already in your wishlist.")
        return

    # Try to fetch the Steam ID from the API
    steam_id = await fetch_steam_id(game_name)
    
    if not steam_id:
        await ctx.send(f"❌ Unable to find **{game_name}** on Steam. Please verify the name.")
        return

    # Add game to Supabase
    data = {"game_name": game_name, "steam_id": steam_id}
    response = supabase.table("wishlist").insert(data).execute()

    if response.data:
        await ctx.send(f"✅ **{game_name}** has been added to your wishlist with Steam ID **{steam_id}**.")
    else:
        await ctx.send(f"❌ Error adding **{game_name}** to the wishlist.")

# Remove Game Command
@bot.command(name='remove')
async def remove_game(ctx, *, game_name: str):
    """Remove a game from the wishlist."""
    existing_game = (
        supabase.table("wishlist")
        .select("game_name")
        .eq("game_name", game_name)
        .execute()
    )

    if not existing_game.data:
        await ctx.send(f"❌ **{game_name}** is not in your wishlist.")
        return

    response = (
        supabase.table("wishlist")
        .delete()
        .eq("game_name", game_name)
        .execute()
    )

    if response.data:
        await ctx.send(f"✅ **{game_name}** has been removed from your wishlist.")
    else:
        await ctx.send(f"❌ Error removing **{game_name}** from the wishlist.")

# List Wishlist Command
@bot.command(name='wishlist')
async def list_wishlist(ctx):
    """Display the current wishlist."""
    wishlist_data = (
        supabase.table("wishlist")
        .select("game_name")
        .execute()
    )

    if not wishlist_data.data:
        await ctx.send("📝 Your wishlist is currently empty.")
        return

    wishlist_text = "\n".join([f"🔹 {game['game_name']}" for game in wishlist_data.data])
    await ctx.send(f"🗂️ **Your Wishlist:**\n{wishlist_text}")

# Run the Bot
bot.run(DISCORD_BOT_TOKEN)
