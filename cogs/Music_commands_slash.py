import nextcord
from nextcord import Interaction
from nextcord.ext import commands
from nextcord import FFmpegPCMAudio
import yt_dlp
import asyncio

class Music_Controller(commands.Cog):
    '''All music controller lies here'''
    def __init__(self,client):
        self.client = client
        self.queues = {} # {id1:[1,2,3,4],id2:[1,2,3,4]}
        self.previous_song = {}
        self.loop = 0
    
    async def play_song(self,interaction,song_url,title,thumbnail,duration): # to play the song
        voice = interaction.guild.voice_client
        
        def after_playing(error):
            nonlocal song_url
            if error:
                print(f"Playback error: {error}")
            elif self.loop == 1:
                source = FFmpegPCMAudio(song_url,before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",options="-vn")
                voice.play(source = source,after=after_playing)                   
            else:
                song_url,title,thumbnail,duration = self.check_queue(interaction.guild_id)
                asyncio.run_coroutine_threadsafe(self.play_song(interaction, song_url, title,thumbnail,duration), self.client.loop)
                
        if song_url != 0:
            embed = nextcord.Embed(title="Now playing:",description=title)
            embed.set_image(url=thumbnail)
            await interaction.send(content="",embed=embed)
            source = FFmpegPCMAudio(song_url,before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",options="-vn")
            voice.play(source = source,after=after_playing)
        else:
            embed = nextcord.Embed(title="Finished playing all songs!")
            await interaction.send(content='',embed=embed)
            asyncio.wait_for(60)
            if not voice.is_playing:
                interaction.guild.voice_client.disconnect()
            return
        
    def check_queue(self,id):
        if self.queues[id] != []:
            song_info = self.queues[id].pop(0)
            try:
                song_url = song_info[0]
                title = song_info[1]
                thumbnail = song_info[2]
                duration = song_info[3]
                self.previous_song[id] = [song_info]
                return song_url,title,thumbnail,duration
            except Exception as e:
                print(f"\nError: {e}\n")
        else:
            return 0,0,0,0
    
    async def addtoqueue(self,interaction,song,sent):
        try:
            downloader = yt_dlp.YoutubeDL({'format': 'bestaudio'})
            song_info = downloader.extract_info(f'ytsearch:{song}', download=False)
            
            song_url = song_info['entries'][0]['url']       
            title = song_info['entries'][0]['title'] 
            thumbnail = song_info['entries'][0]['thumbnail'] 
            duration = song_info['entries'][0]['duration']

            guild_id = interaction.guild_id

            if guild_id in self.queues:
                self.queues[guild_id].append((song_url,title,thumbnail,duration))
            else:
                self.queues[guild_id] = [(song_url,title,thumbnail,duration)]
            
            await sent.edit(content=f"Added `{title}` to queue")
            return

        except Exception as e:
            await sent.edit(f"Error: {e}") 
            return
    
           
    @nextcord.slash_command(name='join',description='Joins the voice channel' )
    async def join(self,interaction:Interaction):
        if (interaction.user.voice):
            channel = interaction.user.voice.channel
            await channel.connect()
            await interaction.send(f"Joined voice channel: {channel}")
        else:
            await interaction.send("You are not in a Voice Channel",delete_after=5)

    @nextcord.slash_command(name='leave',description='Leaves the voice channel and clears the queue' )
    async def leave(self,interaction:Interaction):
        if (interaction.user.voice):
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.disconnect()
                await interaction.send("Left voice channel")
                self.queues = {}
                self.previous_song = {}
            else:
                await interaction.send("Bot not in a voice channel",delete_after=5)
        else:
            await interaction.send("Not in a Voice Channel",delete_after=5)

    @nextcord.slash_command(name='pause',description='Pauses the currently playing song' )
    async def pause(self,interaction:Interaction):
        voice = nextcord.utils.get(self.client.voice_clients,guild = interaction.guild)
        if voice.is_playing():
            voice.pause()
            await interaction.send("Paused",delete_after=10)
        else:
            await interaction.send("No audio is playing",delete_after=5)

    @nextcord.slash_command(name='resume',description='Resumes the current paused song' )
    async def resume(self,interaction:Interaction):
        voice = nextcord.utils.get(self.client.voice_clients,guild = interaction.guild)
        if voice.is_paused():
            voice.resume()
            await interaction.send("Resumed",delete_after=10)
        else:
            await interaction.send("No audio is paused",delete_after=5)
    
    @nextcord.slash_command(name='stop',description='Stops and removes the current song(Stays in the voice channel)' )
    async def stop(self,interaction:Interaction):
        voice = nextcord.utils.get(self.client.voice_clients,guild = interaction.guild) 
        voice.stop()
        voice.pause()
        await interaction.send("Stopped",delete_after=5)
        
    @nextcord.slash_command(name='play',description='Play a song from YouTube or play songs from queue(if added)' )    
    async def play(self, interaction:Interaction, song=""):
        if (interaction.user.voice): # checks if user is in VC
        #--------------------------------------------------                
            if not interaction.guild.voice_client: # checks if bot is in VC
                channel = interaction.user.voice.channel
                await channel.connect() # joins VC
                sent = await interaction.send(f"Joined: {channel}\nGetting the song...")
            else:
                sent = await interaction.send("Getting the song...")
                
        #------------ if no yt link is provided check queue for music --------
            if song == "":  
                song_url,title,thumbnail,duration = self.check_queue(interaction,interaction.guild_id) 
                await self.play_song(interaction,song_url,title,thumbnail,duration)      
                  
        #------------- adds guild id in queue if not present -----------------       
            elif interaction.guild_id not in self.queues:
                self.queues[interaction.guild_id] = []   
                
        #---------------------------------------------------------------------        
            voice = interaction.guild.voice_client  
                
        #-------- if any song is playing the provided song is added to queue ---------        
            if voice.is_playing(): 
                await self.addtoqueue(interaction,song,sent)
                
        #--------------------------------------------------        
            else: 
                try:
                    #--------- download the song from youtube ------------------
                    downloader = yt_dlp.YoutubeDL({'format': 'bestaudio'})
                    song_info = downloader.extract_info(f'ytsearch:{song}', download=False)
            
                    song_url = song_info['entries'][0]['url']       
                    title = song_info['entries'][0]['title']
                    thumbnail = song_info['entries'][0]['thumbnail']
                    duration = song_info['entries'][0]['duration']

                    #--------------- Play the song ------------------
                    # source = FFmpegPCMAudio(source=song_url,before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5")
                    await sent.edit(content="Playing song...")
                    await self.play_song(interaction,song_url,title,thumbnail,duration)
                except:
                    await sent.edit("No such song found!")
                    # await interaction.response.send_message(f"Error: {e}")
        else:
            await interaction.send("You are not in a voice channel",delete_after=10)

    @nextcord.slash_command(name='queue',description='Add song to the queue from youtube by link of it' )
    async def queue(self,interaction:Interaction,link):
        sent = await interaction.send("Adding to queue")
        await self.addtoqueue(interaction,link,sent)
    
    @nextcord.slash_command(name='next',description='Plays the next song' )
    async def next(self,interaction:Interaction):
        voice = interaction.guild.voice_client
        sent = await interaction.send("Playing next song...",delete_after=5)
        if voice.is_playing():
            voice.stop()

    @nextcord.slash_command(name='show_queue',description='Shows all songs added to queue' )
    async def show_queue(self,interaction:Interaction):
        song_list = "Current queue:\n\n"
        for i in range(len(self.queues[interaction.guild_id])):
            song_list += f"{i+1}. {self.queues[interaction.guild_id][i][1]}\n"
        await interaction.send(song_list)
        
    @nextcord.slash_command(name='loop',description='Sets loop to current song' )
    async def loop(self,interaction:Interaction):
        if self.loop == 1:
            self.loop = 0
            await interaction.send("Current song removed from loop!")
        else:
            self.loop = 1
            await interaction.send("Current song set to loop!")
            

def setup(client):
    client.add_cog(Music_Controller(client))
