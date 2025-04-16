# from signal import pause
import nextcord
from nextcord import Interaction
from nextcord.ext import commands, tasks
from nextcord import FFmpegPCMAudio
import yt_dlp
from datetime import timedelta
import random

class Music_Controller(commands.Cog):
    '''All music controller logic lies here'''    
    def __init__(self, client):
        self.client = client
        self.queues = {}  # {guild_id: [(url, title, thumbnail, duration)]}
        self.is_playing = False
        self.paused = True
        self.loopSong = False
        self.player_loop.start()
        self.tips = [
            "Use /play <song name> to play a song from YouTube.",
            "Use /pause to pause the current song.",
            "Use /resume to resume the paused song.",
            "Use /next to skip to the next song in the queue.",
            "Use /queue to see the list of upcoming songs.",
            "Use /loop to toggle looping for the current song.",
            "Use /leave to disconnect from the voice channel and clear the queue.",
            "Use /join to join the voice channel you're in.",
        ]
    


    async def play_song(self, channel, song_url, title, thumbnail, duration):
        # Convert duration in seconds to mm:ss format
        formatted_duration = str(timedelta(seconds=duration))
        embed = nextcord.Embed(
            title="🎶 Now Playing",
            description=f"[{title}]({song_url})",
            color=nextcord.Color.blurple()
        )
        embed.set_image(url=thumbnail)
        embed.add_field(name="⏱ Duration", value=formatted_duration, inline=True)
        embed.set_footer(text=random.choice(self.tips))

        await channel.send(embed=embed)


    def get_next_song(self, guild_id):
        if self.queues.get(guild_id):
            song_info = self.queues[guild_id].pop(0)
            return song_info  # (channel, song_url, title, thumbnail, duration)
        return None

    async def add_to_queue(self, interaction, song, sent):
        try:
            ydl_opts = {
                'format': 'bestaudio[ext=webm]/bestaudio/best',
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
            
            # print(f"Song info: {song_info}")
            
            song_url = song_info['entries'][0]['url']
            title = song_info['entries'][0]['title']
            thumbnail = song_info['entries'][0]['thumbnail']
            duration = song_info['entries'][0]['duration']
            yt_url = song_info['entries'][0]['webpage_url']

            guild_id = interaction.guild.id

            if guild_id not in self.queues:
                self.queues[guild_id] = []
                
            self.queues[guild_id].append((interaction.channel, song_url, title, thumbnail, duration, yt_url))
            
            await sent.edit(content=f"Added `{title}` to queue")

        except Exception as e:
            await sent.edit(content=f"Error: {e}")
        finally:
            self.paused = False

    @tasks.loop(seconds=1)
    async def player_loop(self):
        for guild in self.client.guilds:
            guild_id = guild.id
            voice_client = guild.voice_client

            if voice_client and not self.paused and not self.is_playing:
                self.is_playing = True
                print(f"Guild {guild.name}: Playing next song from queue.")

                song_data = self.get_next_song(guild_id)
                if song_data is None:
                    self.is_playing = False
                    self.paused = True
                    print(f"Guild {guild.name}: No more songs in queue.")
                    continue

                channel, song_url, title, thumbnail, duration, yt_url = song_data
                await self.play_song(channel, yt_url, title, thumbnail, duration) 

                try:
                    voice_client.play(
                        FFmpegPCMAudio(song_url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn -ac 2")
                    )
                except Exception as e:
                    print(f"⚠️ Error starting playback: {e}")



# ================================================= COMMANDS ==================================================== 

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
        voice_client = interaction.guild.voice_client

        if voice_client:
            await voice_client.disconnect()
            self.queues[interaction.guild.id] = []
            self.is_playing = False
            self.paused = True
            await interaction.send("👋 Disconnected and cleared the queue.")
        else:
            await interaction.send("⚠️ I'm not in a voice channel.")


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
            await interaction.send("Resumed", delete_after=5)
        else:
            await interaction.send("No audio is paused", delete_after=5)

    @nextcord.slash_command(name='play', description='Play a song from YouTube or play from queue')
    async def play(self, interaction: Interaction, song: str = ""):
        # Joining the voice channel if not already in one
        if interaction.user.voice:
            if not interaction.guild.voice_client:
                channel = interaction.user.voice.channel
                await channel.connect()
                sent = await interaction.send(f"Joined: {channel}\nGetting the song...")
            else:
                sent = await interaction.send("Getting the song...")

            # If no song is provided, check the queue for the next song
            if song == "":
                self.paused = False                
            else:
                await self.add_to_queue(interaction, song, sent)
                
        # If the user is not in a voice channel, send an error message
        else:
            await interaction.send("You are not in a voice channel", delete_after=10)

    @nextcord.slash_command(name='next', description='Plays the next song in queue')
    async def next(self, interaction: Interaction):
        voice_client = interaction.guild.voice_client
        guild_id = interaction.guild.id
        # Check if the bot is in a voice channel
        if not voice_client:
            await interaction.send("⚠️ I'm not in a voice channel.")
            return
        self.loopSong = False  # Optional: break loop if enabled
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            self.is_playing = False
            self.paused = False
            await interaction.send("⏭️ Playing next song in queue...")
        elif self.queues.get(guild_id):
            self.paused = False
            await interaction.send("▶️ No song was playing, but queue exists — attempting to resume...")
        else:
            await interaction.send("⚠️ There's nothing playing and the queue is empty.")

    @nextcord.slash_command(name='queue', description='Shows all songs in the queue')
    async def show_queue(self, interaction: Interaction):
        guild_id = interaction.guild.id
        song_list = "Current queue:\n\n"
        if self.queues.get(guild_id):
            for i, (_, url, title, _, _, _) in enumerate(self.queues[guild_id]):
                song_list += f"{i+1}. {title}\n"
            await interaction.send(song_list)
        else:
            await interaction.send("Queue is empty!")

    @nextcord.slash_command(name='loop', description='Toggles loop for the current song')
    async def loop(self, interaction: Interaction):
        pass

def setup(client):
    client.add_cog(Music_Controller(client))
