from typing import List, Tuple
from database import UserProfile
import discord

def calculate_similarity(profile1: UserProfile, profile2: UserProfile) -> float:
    total_items1 = len(profile1.games) + len(profile1.artists) + len(profile1.interests)
    total_items2 = len(profile2.games) + len(profile2.artists) + len(profile2.interests)
    
    if total_items1 == 0 or total_items2 == 0:
        return 0.0
    
    common_games = len(set(profile1.games) & set(profile2.games))
    common_artists = len(set(profile1.artists) & set(profile2.artists))
    common_interests = len(set(profile1.interests) & set(profile2.interests))
    
    total_common = common_games + common_artists + common_interests
    average_total = (total_items1 + total_items2) / 2
    
    similarity = total_common / average_total if average_total > 0 else 0.0
    return min(similarity, 1.0)

async def find_matches(user_profile: UserProfile, guild: discord.Guild, threshold: float = 0.3) -> List[Tuple[UserProfile, float]]:
    all_profiles = await UserProfile.find_all_except(user_profile.discord_id)
    matches = []
    
    for other_profile in all_profiles:
        member = guild.get_member(int(other_profile.discord_id))
        if not member:
            continue
            
        similarity = calculate_similarity(user_profile, other_profile)
        if similarity >= threshold:
            matches.append((other_profile, similarity))
    
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches[:5]