from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get Supabase credentials
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_wishlist():
    response = supabase.table("wishlist").select("*").execute()
    return response.data if response.data else []

def add_game_to_wishlist(game_name, steam_id):
    # Check if the game already exists in the wishlist
    existing_game = supabase.table("wishlist").select("*").eq("steam_id", steam_id).execute()

    if existing_game.data:  # If data is returned, the game is already in the wishlist
        print(f"{game_name} is already in the wishlist.")
        return
    
    # Insert new game into wishlist
    data = {"game_name": game_name, "steam_id": steam_id}
    response = supabase.table("wishlist").insert(data).execute()

    if response.data:
        print(f"Added {game_name} to wishlist.")
    else:
        print("Error adding game:", response)

def view_wishlist():
    response = supabase.table("wishlist").select("*").execute()

    if response.data:  # Check if data was retrieved
        games = response.data
        if not games:
            print("Wishlist is empty.")
        else:
            for game in games:
                print(f"{game['game_name']} (Steam ID: {game['steam_id']})")
    else:
        print("Error fetching wishlist:", response)

# Example usage
add_game_to_wishlist("Elden Ring", "1245620")  # Add game
view_wishlist()  # View all games
