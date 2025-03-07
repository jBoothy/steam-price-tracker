import discord
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))

async def send_test_message():
    client = discord.Client(intents=discord.Intents.default())

    @client.event
    async def on_ready():
        channel = client.get_channel(DISCORD_CHANNEL_ID)
        if channel:
            await channel.send("✅ **Test Message:** The bot is working!")
            print("Discord test message sent successfully!")
        await client.close()

    await client.start(DISCORD_BOT_TOKEN)

asyncio.run(send_test_message())
