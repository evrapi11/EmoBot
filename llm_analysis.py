import os
import json
from typing import List, Dict, Any
from openai import AsyncOpenAI
from database import UserProfile

client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

async def extract_interests_from_messages(messages: List[str], existing_profile: UserProfile = None) -> Dict[str, List[str]]:
    """Extract interests from user messages using gpt-4o-mini"""
    
    # Combine messages into context
    message_text = "\n".join(messages[-20:])  # Last 20 messages for context
    
    # Build existing interests context
    existing_context = ""
    if existing_profile:
        existing_games = ", ".join(existing_profile.games) if existing_profile.games else "None"
        existing_artists = ", ".join(existing_profile.artists) if existing_profile.artists else "None" 
        existing_interests = ", ".join(existing_profile.interests) if existing_profile.interests else "None"
        existing_context = f"\nExisting profile:\nGames: {existing_games}\nArtists: {existing_artists}\nInterests: {existing_interests}\n"
    
    prompt = f"""Analyze these Discord messages and extract the user's interests. Only include interests that are clearly expressed or demonstrated.

{existing_context}

Messages:
{message_text}

Extract interests in these categories:
- games: Video games, board games, mobile games
- artists: Musicians, bands, singers (not fictional characters)  
- interests: Hobbies, activities, topics they're passionate about

Rules:
- Only extract NEW interests not already in their profile
- Be conservative - only include clear interests, not casual mentions
- Focus on things they actively enjoy or engage with
- Exclude temporary topics or complaints
- Maximum 3 new items per category

Return as JSON:
{{"games": ["game1", "game2"], "artists": ["artist1"], "interests": ["hobby1", "hobby2"]}}"""

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse JSON response
        if content.startswith('```json'):
            content = content[7:-3]
        elif content.startswith('```'):
            content = content[3:-3]
            
        extracted = json.loads(content)
        
        # Validate structure
        result = {
            "games": extracted.get("games", [])[:3],
            "artists": extracted.get("artists", [])[:3], 
            "interests": extracted.get("interests", [])[:3]
        }
        
        return result
        
    except Exception as e:
        print(f"Error extracting interests: {e}")
        return {"games": [], "artists": [], "interests": []}

async def should_process_messages(messages: List[str]) -> bool:
    """Check if messages contain enough content to warrant analysis"""
    if len(messages) < 3:
        return False
        
    total_length = sum(len(msg) for msg in messages)
    return total_length > 100  # At least 100 characters of content