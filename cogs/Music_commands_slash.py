import nextcord
from nextcord import Interaction
from nextcord.ext import commands
from nextcord import FFmpegPCMAudio
import yt_dlp
import asyncio

class Music_Controller(commands.Cog):
    '''All music controller logic lies here'''
    def __init__(self, client):
        self.client = client
        self.queues = {}  # {guild_id: [(url, title, thumbnail, duration)]}
        self.previous_song = {}
        self.loop = False
    
    async def play_song(self, interaction, song_url, title, thumbnail, duration):
        voice = interaction.guild.voice_client
        
        def after_playing(error):
            nonlocal song_url
            if error:
                print(f"Playback error: {error}")
            elif self.loop:
                source = FFmpegPCMAudio(song_url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn -ac 2")
                voice.play(source=source, after=after_playing)
            else:
                song_url, title, thumbnail, duration = self.check_queue(interaction.guild.id)
                if song_url:
                    asyncio.create_task(self.play_song(interaction, song_url, title, thumbnail, duration))
                
        if song_url:
            embed = nextcord.Embed(title="Now playing:", description=title)
            embed.set_image(url=thumbnail)
            await interaction.send(content="", embed=embed)
            source = FFmpegPCMAudio(song_url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn -ac 2")
            voice.play(source=source, after=after_playing)
        else:
            embed = nextcord.Embed(title="Finished playing all songs!")
            await interaction.send(content='', embed=embed)
            if not voice.is_playing():
                await asyncio.sleep(60)
                if not voice.is_playing():
                    await voice.disconnect()

    def check_queue(self, guild_id):
        if self.queues.get(guild_id):
            song_info = self.queues[guild_id].pop(0)
            self.previous_song[guild_id] = [song_info]
            return song_info
        return None

    async def add_to_queue(self, interaction, song, sent):
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'noplaylist': True,
                'extract_flat': False,
                'default_search': 'auto',
                'source_address': '0.0.0.0',  # Bind to IPv4 to avoid IPv6 issues
                'forceurl': True,
                'skip_download': True
            }
            
            downloader = yt_dlp.YoutubeDL(ydl_opts)

            song_info = downloader.extract_info(f'ytsearch:{song}', download=False)
            
            song_url = song_info['entries'][0]['url']
            title = song_info['entries'][0]['title']
            thumbnail = song_info['entries'][0]['thumbnail']
            duration = song_info['entries'][0]['duration']

            guild_id = interaction.guild.id

            if guild_id not in self.queues:
                self.queues[guild_id] = []
                
            self.queues[guild_id].append((song_url, title, thumbnail, duration))
            
            await sent.edit(content=f"Added `{title}` to queue")

            # If queue was empty before adding the song, play the song immediately
            if len(self.queues[guild_id]) == 1:
                await self.play_song(interaction, song_url, title, thumbnail, duration)

        except Exception as e:
            await sent.edit(content=f"Error: {e}")

    @nextcord.slash_command(name='join', description='Joins the voice channel')
    async def join(self, interaction: Interaction):
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            await channel.connect()
            await interaction.send(f"Joined voice channel: {channel}")
        else:
            await interaction.send("You are not in a Voice Channel", delete_after=5)

    @nextcord.slash_command(name='leave', description='Leaves the voice channel and clears the queue')
    async def leave(self, interaction: Interaction):
        voice = interaction.guild.voice_client
        if voice:
            await voice.disconnect()
            await interaction.send("Left voice channel")
            self.queues = {}
            self.previous_song = {}
        else:
            await interaction.send("Not in a Voice Channel or bot not in a voice channel", delete_after=5)

    @nextcord.slash_command(name='pause', description='Pauses the currently playing song')
    async def pause(self, interaction: Interaction):
        voice = interaction.guild.voice_client
        if voice and voice.is_playing():
            voice.pause()
            await interaction.send("Paused", delete_after=10)
        else:
            await interaction.send("No audio is playing", delete_after=5)

    @nextcord.slash_command(name='resume', description='Resumes the current paused song')
    async def resume(self, interaction: Interaction):
        voice = interaction.guild.voice_client
        if voice and voice.is_paused():
            voice.resume()
            await interaction.send("Resumed", delete_after=10)
        else:
            await interaction.send("No audio is paused", delete_after=5)

    @nextcord.slash_command(name='stop', description='Stops and removes the current song')
    async def stop(self, interaction: Interaction):
        voice = interaction.guild.voice_client
        if voice and voice.is_playing():
            voice.stop()
            await interaction.send("Stopped", delete_after=5)
        else:
            await interaction.send("No audio is playing", delete_after=5)

    @nextcord.slash_command(name='play', description='Play a song from YouTube or play from queue')
    async def play(self, interaction: Interaction, song: str = ""):
        if interaction.user.voice:
            if not interaction.guild.voice_client:
                channel = interaction.user.voice.channel
                await channel.connect()
                sent = await interaction.send(f"Joined: {channel}\nGetting the song...")
            else:
                sent = await interaction.send("Getting the song...")

            if song == "":
                song_data = self.check_queue(interaction.guild.id)
                if song_data:
                    song_url, title, thumbnail, duration = song_data
                    await self.play_song(interaction, song_url, title, thumbnail, duration)
                else:
                    await sent.edit(content="Queue is empty!")
                    return
            else:
                await self.add_to_queue(interaction, song, sent)
        else:
            await interaction.send("You are not in a voice channel", delete_after=10)

    @nextcord.slash_command(name='queue', description='Add song to the queue by YouTube link')
    async def queue(self, interaction: Interaction, link: str):
        sent = await interaction.send("Adding to queue...")
        await self.add_to_queue(interaction, link, sent)

    @nextcord.slash_command(name='next', description='Plays the next song in queue')
    async def next(self, interaction: Interaction):
        voice = interaction.guild.voice_client
        if voice and voice.is_playing():
            voice.stop()
            await interaction.send("Playing next song...", delete_after=5)
        else:
            await interaction.send("No song is currently playing", delete_after=5)

    @nextcord.slash_command(name='show_queue', description='Shows all songs in the queue')
    async def show_queue(self, interaction: Interaction):
        guild_id = interaction.guild.id
        song_list = "Current queue:\n\n"
        if self.queues.get(guild_id):
            for i, (url, title, _, _) in enumerate(self.queues[guild_id]):
                song_list += f"{i+1}. {title}\n"
            await interaction.send(song_list)
        else:
            await interaction.send("Queue is empty!")

    @nextcord.slash_command(name='loop', description='Toggles loop for the current song')
    async def loop(self, interaction: Interaction):
        self.loop = not self.loop
        status = "enabled" if self.loop else "disabled"
        await interaction.send(f"Looping current song is {status}.")

def setup(client):
    client.add_cog(Music_Controller(client))
