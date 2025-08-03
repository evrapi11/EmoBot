import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
from database import UserProfile, init_db
from matching import find_matches, calculate_similarity

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await init_db()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="profile", description="View your profile")
async def profile(interaction: discord.Interaction):
    user_profile = await UserProfile.find_by_discord_id(str(interaction.user.id))
    if not user_profile:
        embed = discord.Embed(title="No Profile Found", description="Use `/add_interest` to start building your profile!", color=0xff0000)
    else:
        embed = discord.Embed(title=f"{interaction.user.display_name}'s Profile", color=0x00ff00)
        if user_profile.games:
            embed.add_field(name="Games", value=", ".join(user_profile.games), inline=False)
        if user_profile.artists:
            embed.add_field(name="Artists", value=", ".join(user_profile.artists), inline=False)
        if user_profile.interests:
            embed.add_field(name="Other Interests", value=", ".join(user_profile.interests), inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="add_interest", description="Add an interest to your profile")
async def add_interest(interaction: discord.Interaction, category: str, interest: str):
    if category.lower() not in ['games', 'artists', 'interests']:
        await interaction.response.send_message("Category must be one of: games, artists, interests", ephemeral=True)
        return
    
    user_profile = await UserProfile.find_by_discord_id(str(interaction.user.id))
    if not user_profile:
        user_profile = UserProfile(
            discord_id=str(interaction.user.id),
            username=interaction.user.display_name,
            games=[],
            artists=[],
            interests=[]
        )
    
    category_list = getattr(user_profile, category.lower())
    if interest.lower() not in [item.lower() for item in category_list]:
        category_list.append(interest)
        await user_profile.save()
        
        matches = await find_matches(user_profile, interaction.guild)
        if matches:
            await notify_matches(user_profile, matches, interaction.guild)
        
        await interaction.response.send_message(f"Added '{interest}' to your {category}!", ephemeral=True)
    else:
        await interaction.response.send_message(f"'{interest}' is already in your {category}!", ephemeral=True)

@bot.tree.command(name="remove_interest", description="Remove an interest from your profile")
async def remove_interest(interaction: discord.Interaction, category: str, interest: str):
    if category.lower() not in ['games', 'artists', 'interests']:
        await interaction.response.send_message("Category must be one of: games, artists, interests", ephemeral=True)
        return
    
    user_profile = await UserProfile.find_by_discord_id(str(interaction.user.id))
    if not user_profile:
        await interaction.response.send_message("You don't have a profile yet!", ephemeral=True)
        return
    
    category_list = getattr(user_profile, category.lower())
    try:
        category_list.remove(interest)
        await user_profile.save()
        await interaction.response.send_message(f"Removed '{interest}' from your {category}!", ephemeral=True)
    except ValueError:
        await interaction.response.send_message(f"'{interest}' not found in your {category}!", ephemeral=True)

async def notify_matches(user_profile, matches, guild):
    user = guild.get_member(int(user_profile.discord_id))
    if not user:
        return
    
    for match_profile, similarity_score in matches:
        match_user = guild.get_member(int(match_profile.discord_id))
        if not match_user:
            continue
        
        try:
            embed = discord.Embed(
                title="🎉 You have a new match!",
                description=f"You have {similarity_score:.1%} similarity with {match_user.display_name}!",
                color=0x00ff00
            )
            
            common_games = set(user_profile.games) & set(match_profile.games)
            common_artists = set(user_profile.artists) & set(match_profile.artists)
            common_interests = set(user_profile.interests) & set(match_profile.interests)
            
            if common_games:
                embed.add_field(name="Common Games", value=", ".join(common_games), inline=False)
            if common_artists:
                embed.add_field(name="Common Artists", value=", ".join(common_artists), inline=False)
            if common_interests:
                embed.add_field(name="Common Interests", value=", ".join(common_interests), inline=False)
            
            await user.send(embed=embed)
            await match_user.send(embed=embed.copy().set_description(f"You have {similarity_score:.1%} similarity with {user.display_name}!"))
            
        except discord.Forbidden:
            print(f"Cannot send DM to {user.display_name} or {match_user.display_name}")

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        print("Please add your Discord bot token to the .env file")
    else:
        bot.run(token)