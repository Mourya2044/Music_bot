import discord
from discord.ext import commands
import os
import asyncio

TOKEN = 'MTEzODQ3MTI1ODk1NTE5NDUwMA.Gte0v4.TyJfnRr36_pBWEs8RJG2406xGdffEp4vvUMCgY'


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

client = commands.Bot(command_prefix='!',intents=intents)

@client.event
async def on_ready():
    await client.change_presence(status=discord.Status.idle,activity=discord.Game('Your Mom!'))
    print("Bot ready")
    print("-----------")
    
initial_extensions=[]  
async def load():
    for filename in os.listdir('cogs'):
        if filename.endswith('.py'):
            extension = 'cogs.'+filename[:-3]
            await client.load_extension(extension)
        
# if __name__ == '__main__':
#     for extension in initial_extensions:
#         client.load_extension(extension) 
 
# async def main():
#     async with client:
#         for extension in initial_extensions:
#             await client.load_extension(extension)
    
async def main():
    await load()
    
asyncio.run(main())
    
client.run(TOKEN)

    