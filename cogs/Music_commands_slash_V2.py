# from signal import pause
import nextcord
from nextcord import Interaction
from nextcord.ext import commands, tasks
from nextcord import FFmpegPCMAudio
import yt_dlp
from datetime import timedelta
import random
import asyncio

class Music_Controller(commands.Cog):
    '''All music controller logic lies here'''    
    def __init__(self, client):
        self.client = client
        self.queues = {}  # {guild_id: [(url, title, thumbnail, duration)]}
        self.is_playing = False
        self.paused = True
        self.loopSong = False
        self.player_loop.start()
        self.adding_playlist_task = None
        self.shuffle = False
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
    
    def get_next_song(self, guild_id):
        if self.queues.get(guild_id):
            if self.shuffle:
                # Pick a random song if shuffle is on
                song_info = random.choice(self.queues[guild_id])
                self.queues[guild_id].remove(song_info)  # Remove the chosen song from the queue
            else:
                # Take the first song from the queue if shuffle is off
                song_info = self.queues[guild_id].pop(0)
            return song_info  # (channel, song_url, title, thumbnail, duration)
        return None

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

    async def add_to_queue(self, interaction, song, sent):
        try:
            ydl_opts = {
                'format': 'bestaudio[ext=webm]/bestaudio/best',
                'quiet': False,
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

    async def add_playlist_to_queue(self, interaction, playlist_url, sent):
        try:
            # Start the playlist addition task
            if self.adding_playlist_task:
                await sent.edit(content="🔴 Playlist addition is already in progress. Please wait or cancel it.")

            # Define cancellation flag
            self.cancel_addition = False

            async def add_songs():
                try:
                    flat_opts = {
                        'quiet': False,
                        'extract_flat': True,
                        'skip_download': True,
                        'forceurl': False,
                    }

                    # Extract list of video entries (flat = metadata only)
                    with yt_dlp.YoutubeDL(flat_opts) as flat_ydl:
                        playlist_info = flat_ydl.extract_info(playlist_url, download=False)

                    entries = playlist_info.get('entries', [])
                    if not entries:
                        await sent.edit(content="⚠️ No songs found in playlist.")
                        return

                    guild_id = interaction.guild.id
                    if guild_id not in self.queues:
                        self.queues[guild_id] = []

                    # Process each video entry individually
                    for i, entry in enumerate(entries):
                        if self.cancel_addition:
                            await sent.edit(content="🛑 Playlist addition canceled.")
                            return

                        try:
                            if not entry:
                                continue
                            # song_url = entry.get('url')
                            title = entry.get('title', 'Unknown Title')

                            await self.add_to_queue(interaction, title, sent)

                            # Send message for each song added
                            await interaction.channel.send(f"✅ Added `{title}` to queue ({i + 1}/{len(entries)})")

                        except Exception as e:
                            print(f"⚠️ Failed to process song: {e}")
                            continue

                    await sent.edit(content=f"✅ Finished adding {len(self.queues[guild_id])} songs from playlist.")
                    self.paused = False

                except Exception as e:
                    await sent.edit(content=f"❌ Error adding playlist: {e}")

            # Start the task to add songs
            self.adding_playlist_task = asyncio.create_task(add_songs())

        except Exception as e:
            await sent.edit(content=f"❌ Error: {e}")

    async def cancel_addition(self, interaction, sent):
        # Cancel the ongoing playlist addition task
        if self.adding_playlist_task and not self.adding_playlist_task.done():
            self.cancel_addition = True
            await sent.edit(content="🛑 Playlist addition has been canceled.")
            self.adding_playlist_task.cancel()  # Cancel the task
        else:
            await sent.edit(content="❌ No ongoing playlist addition to cancel.")
    
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
                
                def after_play(error):
                    if error:
                        print(f"Error playing song: {error}")
                    self.is_playing = False
                
                try:
                    voice_client.play(
                        FFmpegPCMAudio(song_url, before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", options="-vn -ac 2"),
                        after=after_play
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
    async def play(self, interaction: Interaction, song: str):
        # Joining the voice channel if not already in one
        if interaction.user.voice:
            if not interaction.guild.voice_client:
                channel = interaction.user.voice.channel
                await channel.connect()
                sent = await interaction.send(f"Joined: {channel}\nGetting the song...")
            else:
                sent = await interaction.send("Getting the song...")

            await self.add_to_queue(interaction, song, sent)
                
        # If the user is not in a voice channel, send an error message
        else:
            await interaction.send("You are not in a voice channel", delete_after=10)

    @nextcord.slash_command(name='playlist', description='Play a playlist from YouTube')
    async def playlist(self, interaction: Interaction, playlist_url: str):
        # Joining the voice channel if not already in one
        if interaction.user.voice:
            if not interaction.guild.voice_client:
                channel = interaction.user.voice.channel
                await channel.connect()
                sent = await interaction.send(f"Joined: {channel}\nAdding playlist...")
            else:
                sent = await interaction.send("Adding playlist...")

            await self.add_playlist_to_queue(interaction, playlist_url, sent)
                
        # If the user is not in a voice channel, send an error message
        else:
            await interaction.send("You are not in a voice channel", delete_after=10)
    
    @nextcord.slash_command(name='cancel_addition', description='Cancel the ongoing playlist addition')
    async def cancel_addition(self, interaction: Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client:
            sent = await interaction.send("Canceling playlist addition...")
            await self.cancel_addition(interaction, sent)
        else:
            await interaction.send("⚠️ I'm not in a voice channel.")
            
    @nextcord.slash_command(name='shuffle', description='Toggles shuffle mode')
    async def toggle_shuffle(self, interaction: Interaction):
        self.shuffle = not self.shuffle  # Toggle shuffle mode
        status = "enabled" if self.shuffle else "disabled"
        await interaction.send(f"Shuffle mode has been {status}.")
    
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
        song_list = "Current queue:\nshuffle: {}\n\n".format("enabled" if self.shuffle else "disabled")
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
