import os
from apify_client import ApifyClient
from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(REPO_ROOT, ".env"))

# Initialize with your personal API token
client = ApifyClient(os.getenv("ALL_TRAILS_API_KEY"))

if __name__ == "__main__":
    run_input = {
        "mode": "searchTrails",            
        "query": "Lake Daniells Track",
        "country": "new-zealand",                  # Forces the search scope to the US index
        "fetchTrailDetails": True,         # CRITICAL: Pulls length and elevation gain fields
    }
    
    print("Running scraper... please wait (this takes a moment to bypass blocks).")
    run = client.actor("crawlerbros/alltrails-scraper").call(run_input=run_input)
    
    dataset = client.dataset(run["defaultDatasetId"])
    items = list(dataset.iterate_items())
    
    if not items:
        print("No trails found. Check your Apify proxy balance or try adjusting the query name.")
    
    for trail in items:
        print("\n--- Trail Found ---")
        print(f"Trail Name:     {trail.get('name')}")
        print(f"Area / Park:    {trail.get('areaName', 'N/A')}")
        print(f"Location:       {trail.get('city')}, {trail.get('state')}")
        
        # Pulling the correct explicit metrics keys
        print(f"Length:         {trail.get('lengthMiles')} miles ({trail.get('lengthKm')} km)")
        print(f"Elevation Gain: {trail.get('elevationGainFeet')} ft ({trail.get('elevationGainMeters')} m)")
        
        print(f"Difficulty:     {trail.get('difficulty')}")
        print(f"Route Type:     {trail.get('routeType')}")