import nextcord
from nextcord import Interaction
from nextcord.ext import commands
import os
from dotenv import load_dotenv


load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')


intents = nextcord.Intents.default()
intents.members = True
intents.message_content = True

client = commands.Bot(intents=intents)

@client.event
async def on_ready():
    await client.change_presence(status=nextcord.Status.idle,activity=nextcord.Game('Music'))
    print("Bot ready")
    print("-----------")

 
@client.slash_command(name = "ping",description="Introduction to slash command")
async def test(interaction: Interaction):
    await interaction.response.send_message("Pong!")
 

initial_extensions=[]  
# def load():
#     for filename in os.listdir('cogs'):
#         if filename.endswith('.py'):
#             extension = 'cogs.'+filename[:-3]
#             client.load_extension(extension)
#     return

    
# load()

client.load_extension("cogs.Music_commands_slash_V2")    
client.run(TOKEN)

    