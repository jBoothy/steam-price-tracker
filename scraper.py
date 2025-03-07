import requests
import os
import smtplib
import discord
from email.message import EmailMessage
from wishlist import get_wishlist
from supabase import create_client, Client
from dotenv import load_dotenv
import asyncio
import aiohttp
import matplotlib.pyplot as plt
from datetime import datetime
from dateutil import parser
import matplotlib.dates as mdates
import warnings
warnings.filterwarnings("ignore", category=ResourceWarning)

PERCENTAGE_THRESHOLD = 20

# Load environment variables
load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Email Config
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Discord Config
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

def get_steam_price(steam_id):
    """Fetch game price from Steam API."""
    url = f"https://store.steampowered.com/api/appdetails?appids={steam_id}&l=english"
    response = requests.get(url)

    if response.status_code != 200:
        return f"Failed to fetch data: {response.status_code}"

    data = response.json()
    
    if not data[str(steam_id)]["success"]:
        return "Game not found in Steam API"

    try:
        price_info = data[str(steam_id)]["data"]["price_overview"]
        return price_info['final_formatted']
    except KeyError:
        return "Price not found (might be free or unavailable)"

def send_email(game_name, price):
    """Send an email notification if a price drop is detected."""
    msg = EmailMessage()
    msg["Subject"] = f"Price Drop Alert: {game_name} is now {price}!"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = EMAIL_ADDRESS
    msg.set_content(f"The game {game_name} has dropped in price to {price}.\n\nCheck it out on Steam!")

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
        print(f"Email sent for {game_name} - {price}")
    except Exception as e:
        print("Error sending email:", e)
        
async def check_for_sale_events():
    """Check if a Steam sale is currently active and notify users."""
    current_date = datetime.now()

    # Example sale periods (replace with actual dates or use Steam's API)
    sale_start_summer = datetime(2025, 6, 25)  # Example: Steam Summer Sale start date
    sale_end_summer = datetime(2025, 7, 9)  # Example: Steam Summer Sale end date
    sale_start_winter = datetime(2025, 12, 22)  # Example: Steam Winter Sale start date
    sale_end_winter = datetime(2025, 12, 31)  # Example: Steam Winter Sale end date

    if sale_start_summer <= current_date <= sale_end_summer:
        # Notify users of the ongoing sale
        await send_discord_notification("Steam Summer Sale", "Check out discounts during the Summer Sale!")
    elif sale_start_winter <= current_date <= sale_end_winter:
        await send_discord_notification("Steam Winter Sale", "Check out discounts during the Winter Sale!")
    else:
        print("❌ No sales event currently active.")

async def generate_price_history_graph(game_name, steam_id):
    """Generate a graph showing the price history of a game."""

    # Fetch all historical prices from Supabase
    price_data = (
        supabase.table("price_history")
        .select("price", "checked_at")
        .eq("steam_id", steam_id)
        .order("checked_at", desc=False)
        .execute()
    )

    if not price_data.data:
        print(f"❌ No price history found for {game_name}")
        return None

    # Extract data for the graph
    dates = [parser.parse(entry["checked_at"]) for entry in price_data.data]
    prices = [float(entry["price"].replace("$", "").replace(",", "")) for entry in price_data.data]

    # Generate the graph
    plt.figure(figsize=(10, 5))  # Increase graph size for readability
    plt.plot(dates, prices, marker='o', linestyle='-', label='Price History')
    
    # Improved Date Formatting
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%b %d\n%H:%M'))  # Date + Time
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())  # Auto spacing
    plt.gcf().autofmt_xdate()  # Rotate labels for better spacing

    plt.title(f"Price History for {game_name}")
    plt.xlabel("Date")
    plt.ylabel("Price (USD)")
    plt.grid(True)
    plt.tight_layout()

    # Save the graph as an image file
    graph_path = f"{game_name}_price_history.png"
    plt.savefig(graph_path)
    plt.close()

    print(f"📊 Price history graph generated for {game_name}")
    return graph_path

async def send_discord_notification(game_name, price, steam_id):
    """Send a Discord notification if a price drops."""
    
    graph_path = await generate_price_history_graph(game_name, steam_id)

    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        channel = client.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=f"Price Drop Alert! 🚨",
                description=f"**{game_name}** is now **${price}** on Steam!",
                color=0x57F287
            )
            embed.add_field(
                name="🔗 Link",
                value=f"[Check it out here](https://store.steampowered.com/app/{steam_id}/)",
                inline=False
            )

            # Attach the graph if available
            if graph_path:
                file = discord.File(graph_path, filename="price_history.png")
                embed.set_image(url=f"attachment://price_history.png")
                await channel.send(embed=embed, file=file)
            else:
                await channel.send(embed=embed)

            print(f"✅ Discord notification sent for {game_name} - {price}")
        
        await client.close()

    try:
        await client.start(DISCORD_BOT_TOKEN)
    except Exception as e:
        print(f"Error sending Discord notification: {e}")
    finally:
        if not client.is_closed():
            await client.close()

async def check_wishlist_prices():
    wishlist = get_wishlist()
    if not wishlist:
        print("Your wishlist is empty.")
        return

    for game in wishlist:
        steam_id = game["steam_id"]
        game_name = game["game_name"]
        price = get_steam_price(steam_id)

        print(f"{game_name} - {price}")
        await save_price_to_db(game_name, steam_id, price)  # Use 'await' here

async def save_price_to_db(game_name, steam_id, price):
    """Save the price history to Supabase and send Discord notification if a significant price drop occurs."""
    
    # Fetch the last recorded price from the database
    last_price_data = (
        supabase.table("price_history")
        .select("price", "lowest_price")
        .eq("steam_id", steam_id)
        .order("checked_at", desc=True)
        .limit(1)
        .execute()
    )

    # Get the last and lowest recorded prices
    last_price = last_price_data.data[0]["price"] if last_price_data.data else None
    lowest_price = last_price_data.data[0]["lowest_price"] if last_price_data.data and "lowest_price" in last_price_data.data[0] else None

    print(f"🔍 DEBUG: Last recorded price for {game_name} = {last_price}")
    print(f"🔍 DEBUG: New price for {game_name} = {price}")
    print(f"🔍 DEBUG: Lowest recorded price for {game_name} = {lowest_price}")

    # Ensure prices are compared as numbers
    try:
        last_price = float(last_price.replace("$", "").replace(",", "")) if isinstance(last_price, str) else last_price
        price = float(price.replace("$", "").replace(",", ""))
        if lowest_price is not None and isinstance(lowest_price, str):
            lowest_price = float(lowest_price.replace("$", "").replace(",", ""))
    except ValueError:
        print("⚠️ Price conversion error — data may be malformed.")
        return

    # Save the new price to the database
    data = {
        "game_name": game_name,
        "steam_id": steam_id,
        "price": price,
        "lowest_price": min(price, lowest_price) if lowest_price else price  # Store lowest price
    }
    response = supabase.table("price_history").insert(data).execute()

    if response.data:
        print(f"Saved price for {game_name}: {price}")
        
        # Check for a significant price drop
        if last_price:
            percentage_drop = ((last_price - price) / last_price) * 100
            print(f"🔎 DEBUG: {game_name} price dropped by {percentage_drop:.2f}%")

            if percentage_drop >= PERCENTAGE_THRESHOLD:
                print(f"💰 Significant price drop detected for {game_name} - Previous: {last_price} | Now: {price}")
                await send_discord_notification(game_name, price, steam_id)
        else:
            print(f"📉 No previous price for {game_name}, no price drop alert.")
        
        # Notify if new price matches or beats the lowest price ever
        if lowest_price is None or price < lowest_price:
            print(f"🏅 New all-time low price for {game_name}! Previous Lowest: {lowest_price if lowest_price else 'N/A'} | Now: {price}")
            await send_discord_notification(game_name, price, steam_id)
        else:
            print(f"📉 Price is higher than the lowest recorded price for {game_name}. No alert sent.")
    else:
        print(f"❌ Error saving price for {game_name}:", response)

async def main():
    """Main async function to handle flow."""
    await check_for_sale_events()
    await check_wishlist_prices()

# Run the main async function
asyncio.run(main())
