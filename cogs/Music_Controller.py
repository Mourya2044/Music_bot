import discord
from discord.ext import commands
from pydub import AudioSegment
from pydub.playback import play
import yt_dlp
import requests
from io import BytesIO
import asyncio

class Music_Controller(commands.Cog):
    '''All music controller lies here'''
    def __init__(self,client):
        self.client = client
        self.queues = {}

    async def show_title(self,ctx,title):
        await ctx.send(f"Now playing: {title}")
    
    def check_queue(self,ctx,id):
        if self.queues[id] != []:
            voice = ctx.guild.voice_client
            if self.queues[id] != []:
                song_info = self.queues[id].pop(0)
                source = song_info[0]
                title = song_info[1]
                asyncio.run(self.show_title(title))
                voice.play(source,after= lambda x=None:self.check_queue(ctx,ctx.message.guild.id))
            else:
                return
    
    
            
    @commands.command(pass_context = True)
    async def join(self,ctx):
        '''Joins the voice channel'''
        if (ctx.author.voice):
            channel = ctx.message.author.voice.channel
            await channel.connect()
            await ctx.send(f"Joined voice channel: {channel}")
        else:
            await ctx.send("You are not in a Voice Channel")

    @commands.command(pass_context = True)
    async def leave(self,ctx):
        '''Leaves the voice channel and clears the queue'''
        if (ctx.voice_client):
            await ctx.guild.voice_client.disconnect()
            await ctx.send("Left voice channel")
            self.queues = {}
        else:
            await ctx.send("Not in a Voice Channel")

    @commands.command(pass_context = True)
    async def pause(self,ctx):
        '''Pauses the currently playing song'''
        voice = discord.utils.get(self.client.voice_clients,guild = ctx.guild)
        if voice.is_playing():
            voice.pause()
        else:
            await ctx.send("No audio is playing")

    @commands.command(pass_context = True)
    async def resume(self,ctx):
        '''Resumes the current paused song'''
        voice = discord.utils.get(self.client.voice_clients,guild = ctx.guild)
        if voice.is_paused():
            voice.resume()
        else:
            await ctx.send("No audio is paused")
    
    @commands.command(pass_context = True)
    async def stop(self,ctx):
        '''Stops and removes the current song(Stays in the voice channel)'''
        voice = discord.utils.get(self.client.voice_clients,guild = ctx.guild)  
        voice.stop()

        
    @commands.command(pass_context=True)
    async def play(self, ctx, arg=""):
        '''Play a song from youtube by link of it'''
        if ctx.author.voice:
            if ctx.voice_client is None:  # If not in a voice channel, connect to the user's channel
                channel = ctx.message.author.voice.channel
                await channel.connect()

            voice = ctx.guild.voice_client
            if arg == "":
                self.check_queue(ctx, ctx.message.guild.id)  # Play the next song in queue
            elif voice.is_playing():
                await self.addtoqueue(ctx, arg)  # Add the requested song to the queue
            else:
                try:
                    downloader = yt_dlp.YoutubeDL({'format': 'bestaudio'})
                    r = downloader.extract_info(arg, download=False)

                    audio_url = r['url']
                    

                    source = discord.FFmpegPCMAudio(audio_url)

                    title = r.get('title')
                    await ctx.send(f"Now playing: {title}")
                    voice.play(source, after=lambda x=None: self.check_queue(ctx, ctx.message.guild.id))
                except Exception as e:
                    await ctx.send(f"An error occurred: {str(e)}")
        else:
            await ctx.send("You are not in a voice channel")

    
    async def addtoqueue(self,ctx,arg):
        downloader = yt_dlp.YoutubeDL({'format': 'bestaudio'})
        r = downloader.extract_info(arg, download=False) 
        source = AudioSegment.from_file(
            r.get('url'), before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
        )
        title = r.get('title')
        
        guild_id = ctx.message.guild.id

        if guild_id in self.queues:
            self.queues[guild_id].append((source,title))
        else:
            self.queues[guild_id] = [(source,title)]
        
        await ctx.send("Added to queue")
    
        
    @commands.command(pass_context = True)
    async def queue(self,ctx,arg):
        '''Add song to the queue from youtube by link of it'''
        self.addtoqueue(ctx,arg)
    
    @commands.command()
    async def next(self,ctx):
        '''Plays the next song'''
        voice = discord.utils.get(self.client.voice_clients,guild = ctx.guild)
        if voice.is_playing():
            voice.stop()

        self.check_queue(ctx,ctx.message.guild.id)


        

    @commands.command()
    async def show_queue(self,ctx):
        '''Shows all songs added to queue'''
        song_list = "Current queue:\n\n"
        for i in range(len(self.queues[ctx.message.guild.id])):
            song_list += f"{i+1}. {self.queues[ctx.message.guild.id][i][1]}\n"
        await ctx.send(song_list)
        

async def setup(client):
    await client.add_cog(Music_Controller(client))
