# from signal import pause
import nextcord
from nextcord import Interaction, SlashOption
from nextcord.ext import commands, tasks
from nextcord import FFmpegPCMAudio
import yt_dlp
from datetime import timedelta
import random
import asyncio
import os
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth


load_dotenv()
client_id=os.getenv('SPOTIFY_CLIENT_ID')
client_secret=os.getenv('SPOTIFY_CLIENT_SECRET')
# cookies=os.getenv('COOKIES')

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri="http://localhost:8080",
    scope="playlist-read-private playlist-read-collaborative"
))

class Music_Controller(commands.Cog):
    '''All music controller logic lies here'''    
    def __init__(self, client):
        """Initialize the Music_Controller cog"""
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
            "Use /playlist <playlist URL> to play a YouTube playlist.",
            "Use /shuffle to toggle shuffle mode.",
            "Use /cancel_addition to cancel the ongoing playlist addition.",
            "Use /pause to pause the current song.",
            "Use /resume to resume the paused song.",
            "Use /next to skip to the next song in the queue.",
            "Use /queue to see the list of upcoming songs.",
            "Use /loop to toggle looping for the current song.",
            "Use /leave to disconnect from the voice channel and clear the queue.",
            "Use /join to join the voice channel you're in.",
        ]
    
    def _get_next_song(self, guild_id):
        """ Get the next song from the queue """
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
    
    def _download_song_info(self, song, ydl_opts):
        """Download song info using yt-dlp"""
        downloader = yt_dlp.YoutubeDL(ydl_opts)
        return downloader.extract_info(f'ytsearch:{song}', download=False)
    
    async def _song_card(self, channel, yt_url, title, thumbnail, duration):
        """ Create a song card and send it to the channel """
        # Convert duration in seconds to mm:ss format
        formatted_duration = str(timedelta(seconds=duration))
        embed = nextcord.Embed(
            title="🎶 Now Playing",
            description=f"[{title}]({yt_url})",
            color=nextcord.Color.blurple()
        )
        embed.set_image(url=thumbnail)
        embed.add_field(name="⏱ Duration", value=formatted_duration, inline=True)
        embed.set_footer(text=random.choice(self.tips))

        await channel.send(embed=embed)

    async def _add_to_queue(self, interaction, song, sent):
        """ Adds a song to the queue and fetches its info """
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
            
            # downloader = yt_dlp.YoutubeDL(ydl_opts)

            song_info = await asyncio.to_thread(self._download_song_info, song, ydl_opts)
            
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

    async def _add_playlist_to_queue(self, interaction, playlist_url, sent, start, limit):
            """Main entry point for adding playlists to the queue"""
            try:
                if self.adding_playlist_task and not self.adding_playlist_task.done():
                    await sent.edit(content="🔴 Playlist addition is already in progress. Please wait or cancel it.")
                    return

                self.cancel_addition = False
                self.adding_playlist_task = asyncio.create_task(
                    self._process_playlist_addition(interaction, playlist_url, sent, start, limit)
                )

            except Exception as e:
                await sent.edit(content=f"❌ Initialization Error: {e}")

    async def _process_playlist_addition(self, interaction, playlist_url, sent, start, limit):
            """Handles the actual playlist processing"""
            try:
                # Determine playlist type and get titles
                if "spotify.com" in playlist_url:
                    titles = await self._get_spotify_titles(playlist_url, start, limit)
                elif "youtube.com" in playlist_url or "youtu.be" in playlist_url:
                    titles = await self._get_youtube_titles(playlist_url, start, limit)
                else:
                    await sent.edit(content="❌ Unsupported playlist platform")
                    return

                if not titles:
                    await sent.edit(content="⚠️ No tracks found in playlist")
                    return

                # Add tracks to queue
                added_count = await self._add_tracks_from_list(interaction, titles, sent)
                await sent.edit(content=f"✅ Added {added_count} tracks to queue")

            except Exception as e:
                await sent.edit(content=f"❌ Processing Error: {e}")
            finally:
                self.adding_playlist_task = None

    async def _get_spotify_titles(self, playlist_url, start, limit):
            """Get track titles from Spotify playlist with pagination"""
            try:
                playlist_id = playlist_url.split("/")[-1].split("?")[0]
                titles = []
                remaining = limit
                offset = start

                while remaining > 0:
                    # Get up to 100 tracks per request (Spotify's max)
                    batch_limit = min(remaining, 100)

                    results = sp.playlist_items(
                        playlist_id,
                        fields="items.track.name,total,next",
                        limit=batch_limit,
                        offset=offset
                    )

                    batch = [
                        item['track']['name']
                        for item in results["items"]
                        if item["track"]
                    ]
                    titles.extend(batch)

                    # Update counters
                    fetched = len(batch)
                    remaining -= fetched
                    offset += fetched

                    # Break if no more tracks or partial response
                    if fetched < batch_limit:
                        break
                    
                return titles[:limit]  # Ensure we don't exceed requested limit

            except Exception as e:
                print(f"Spotify Error: {e}")
                return []

    async def _get_youtube_titles(self, playlist_url, start, limit):
            """Get video titles from YouTube playlist with slicing"""
            try:
                ydl_opts = {
                    'quiet': True,
                    'extract_flat': True,
                    'skip_download': True,
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(playlist_url, download=False)
                    all_entries = [entry.get('title') 
                                  for entry in info.get('entries', []) 
                                  if entry]

                    # Apply start/limit with bounds checking
                    end_index = start + limit
                    return all_entries[start:end_index]

            except Exception as e:
                print(f"YouTube Error: {e}")
                return []

    async def _add_tracks_from_list(self, interaction, titles, sent):
            """Add tracks to queue with progress tracking"""
            guild_id = interaction.guild.id
            self.queues.setdefault(guild_id, [])
            added_count = 0

            for i, title in enumerate(titles, 1):
                if self.cancel_addition:
                    await sent.edit(content="🛑 Addition cancelled")
                    self.cancel_addition = False
                    return added_count

                try:
                    await self._add_to_queue(interaction, title, sent)
                    added_count += 1

                    # Update progress every 10 tracks or on last track
                    if i % 10 == 0 or i == len(titles):
                        await sent.edit(
                            content=f"⏳ Adding tracks... ({i}/{len(titles)})"
                        )

                except Exception as e:
                    print(f"Skipped track {title}: {e}")

            return added_count   
        
    async def _cancel_addition_playlist(self, interaction, sent):
        """Cancel the ongoing playlist addition task"""
        # Cancel the ongoing playlist addition task
        if self.adding_playlist_task and not self.adding_playlist_task.done():
            self.cancel_addition = True
            await sent.edit(content="🛑 Playlist addition has been canceled.")
            self.adding_playlist_task.cancel()  # Cancel the task
        else:
            await sent.edit(content="❌ No ongoing playlist addition to cancel.")
    
    @tasks.loop(seconds=1)
    async def player_loop(self):
        """Main loop for playing songs"""
        for guild in self.client.guilds:
            guild_id = guild.id
            voice_client = guild.voice_client

            if voice_client and not self.paused and not self.is_playing:
                self.is_playing = True
                print(f"Guild {guild.name}: Playing next song from queue.")

                song_data = self._get_next_song(guild_id)
                if song_data is None:
                    self.is_playing = False
                    self.paused = True
                    print(f"Guild {guild.name}: No more songs in queue.")
                    continue

                channel, song_url, title, thumbnail, duration, yt_url = song_data
                await self._song_card(channel, yt_url, title, thumbnail, duration) 
                
                async def after_play(error):
                    if error:
                        print(f"Error playing song: {error}")
                    if self.queues[guild_id].__len__() == 0:
                        self.is_playing = False
                        self.paused = True
                        await channel.send("`⏭️ Queue is empty.`")
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
        """Join the voice channel of the user"""
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            await channel.connect()
            await interaction.send(f"Joined voice channel: {channel}")
        else:
            await interaction.send("You are not in a Voice Channel", delete_after=5)

    @nextcord.slash_command(name='leave', description='Leaves the voice channel and clears the queue')
    async def leave(self, interaction: Interaction):
        """Leave the voice channel and clear the queue"""
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
        """Pause the currently playing song"""
        voice = interaction.guild.voice_client
        if voice.is_paused():
            await interaction.send("Already paused.", delete_after=5)
            return
        if voice and voice.is_playing():
            voice.pause()
            await interaction.send("Paused", delete_after=10)
        else:
            await interaction.send("No audio is playing", delete_after=5)

    @nextcord.slash_command(name='resume', description='Resumes the current paused song')
    async def resume(self, interaction: Interaction):
        """Resume the currently paused song"""
        voice = interaction.guild.voice_client
        if voice and voice.is_paused():
            voice.resume()
            await interaction.send("Resumed", delete_after=5)
        else:
            await interaction.send("No audio is paused", delete_after=5)

    @nextcord.slash_command(name='play', description='Play a song by Name')
    async def play(self, interaction: Interaction, song: str = SlashOption(description="The name of the song", required=True)):
        """Play a song from YouTube"""
        # Joining the voice channel if not already in one
        if interaction.user.voice:
            if not interaction.guild.voice_client:
                channel = interaction.user.voice.channel
                await channel.connect()
                sent = await interaction.send(f"Joined: {channel}\nGetting the song: `{song}`")
            else:
                sent = await interaction.send(f"Getting the song: `{song}`")

            await self._add_to_queue(interaction, song, sent)
                
        # If the user is not in a voice channel, send an error message
        else:
            await interaction.send("You are not in a voice channel", delete_after=10)

    @nextcord.slash_command(name='playlist', description='Play a playlist from YouTube or Spotify')
    async def playlist(self, interaction: Interaction, playlist_url: str = SlashOption(description="The URL of the playlist", required=True), start: int = SlashOption(description="The starting index of the playlist", required=False, default=0), limit: int = SlashOption(description="The number of tracks to play", required=False, default=10)):
        """Play tracks from a playlist with optional start/limit parameters"""
        # Validate parameters
        if start < 0:
            await interaction.send("❌ Start index cannot be negative", delete_after=10)
            return
        if limit <= 0:
            await interaction.send("❌ Limit must be at least 1", delete_after=10)
            return

        # Check voice channel
        if not interaction.user.voice:
            await interaction.send("❌ You must be in a voice channel", delete_after=10)
            return

        # Join voice channel if needed
        if not interaction.guild.voice_client:
            channel = interaction.user.voice.channel
            await channel.connect()
            sent = await interaction.send(f"🔊 Joined {channel.mention}\n⏳ Loading playlist...")
        else:
            sent = await interaction.send("⏳ Loading playlist...")

        # Start playlist processing
        await self._add_playlist_to_queue(interaction, playlist_url, sent, start, limit)
    
    @nextcord.slash_command(name='cancel_addition', description='Cancel the ongoing playlist addition')
    async def cancel_addition(self, interaction: Interaction):
        """Cancel the ongoing playlist addition"""
        voice_client = interaction.guild.voice_client
        if voice_client:
            sent = await interaction.send("Canceling playlist addition...")
            await self._cancel_addition_playlist(interaction, sent)
        else:
            await interaction.send("⚠️ I'm not in a voice channel.")
            
    @nextcord.slash_command(name='shuffle', description='Toggles shuffle mode')
    async def toggle_shuffle(self, interaction: Interaction):
        """Toggle shuffle mode for the queue"""
        self.shuffle = not self.shuffle  # Toggle shuffle mode
        status = "enabled" if self.shuffle else "disabled"
        await interaction.send(f"Shuffle mode has been {status}.")
    
    @nextcord.slash_command(name='next', description='Plays the next song in queue')
    async def next(self, interaction: Interaction):
        """Play the next song in the queue"""
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
        """Show the current queue of songs"""
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
        """Toggle loop for the current song"""
        self.loopSong = not self.loopSong
        status = "enabled" if self.loopSong else "disabled"
        await interaction.send(f"Loop mode has been {status}.", delete_after=5)

def setup(client):
    """Load the Music_Controller cog"""
    client.add_cog(Music_Controller(client))
