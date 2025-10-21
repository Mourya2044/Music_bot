import nextcord
from nextcord import Interaction
from nextcord.ext import commands
import os
from dotenv import load_dotenv
from flask import Flask
from multiprocessing import Process

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# ---- Flask web server to keep app alive ----
# app = Flask(__name__)
# @app.route('/')
# def home():
#     return "Bot is running!"

# def run_flask():
#     app.run(host='0.0.0.0', port=8000, use_reloader=False)

# Process(target=run_flask).start()

# ---- Discord Bot ----
intents = nextcord.Intents.default()
intents.members = True
intents.message_content = True
client = commands.Bot(intents=intents)

@client.event
async def on_ready():
    await client.change_presence(status=nextcord.Status.idle, activity=nextcord.Game('Music'))
    print("Bot ready")
    print("-----------")

@client.slash_command(name="ping", description="Pongs you back")
async def test(interaction: Interaction):
    await interaction.response.send_message("Pong!")

client.load_extension("cogs.Music_commands_slash_V2")

client.run(TOKEN)
