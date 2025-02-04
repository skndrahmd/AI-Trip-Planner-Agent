import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import urllib.parse
import requests

# Load environment variables
load_dotenv()

# Configure OpenAI
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Google Maps API Key
GOOGLE_MAPS_API_KEY = st.secrets["GOOGLE_MAPS_API_KEY"]
if not GOOGLE_MAPS_API_KEY:
    st.error("Google Maps API key not found. Please add GOOGLE_MAPS_API_KEY to your .env file.")
    st.stop()

def validate_coordinates(lat, lng):
    """Validate if coordinates are within reasonable bounds for Earth."""
    try:
        lat = float(lat)
        lng = float(lng)
        # Check if coordinates are within Earth's bounds
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return False
        return True
    except:
        return False

def extract_location_from_prompt(prompt):
    """Extract the target location from the user's prompt."""
    try:
        print(f"\n--- Extracting location from prompt: {prompt} ---")
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Extract only the main location (city/region/country) from the travel query. Respond with ONLY the location name, nothing else."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        location = response.choices[0].message.content.strip()
        print(f"Extracted location: {location}")
        return location
    except Exception as e:
        st.error(f"Error extracting location: {str(e)}")
        print(f"Error in extract_location_from_prompt: {str(e)}")
        return None

def validate_place_with_google_maps(place_name, location):
    """Validate coordinates using Google Maps Places API for more accurate results."""
    try:
        # First try to find the place using Places API Text Search
        search_query = f"{place_name}, {location}"
        places_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={urllib.parse.quote(search_query)}&key={GOOGLE_MAPS_API_KEY}"
        response = requests.get(places_url)
        data = response.json()
        
        if data['status'] == 'OK' and len(data['results']) > 0:
            # Get the place_id from the first result
            place_id = data['results'][0]['place_id']
            
            # Use Place Details API to get more accurate information
            details_url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,formatted_address,geometry,url,photos&key={GOOGLE_MAPS_API_KEY}"
            details_response = requests.get(details_url)
            details_data = details_response.json()
            
            if details_data['status'] == 'OK':
                result = details_data['result']
                google_lat = result['geometry']['location']['lat']
                google_lng = result['geometry']['location']['lng']
                formatted_address = result.get('formatted_address', '')
                maps_url = result.get('url', '')
                
                # Get the first photo reference if available
                photo_url = None
                if 'photos' in result and len(result['photos']) > 0:
                    photo_ref = result['photos'][0]['photo_reference']
                    photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photo_reference={photo_ref}&key={GOOGLE_MAPS_API_KEY}"
                
                print(f"Found coordinates for {place_name}:")
                print(f"Address: {formatted_address}")
                print(f"Google Maps: {google_lat}, {google_lng}")
                print(f"Place ID: {place_id}")
                print(f"Maps URL: {maps_url}")
                
                return True, google_lat, google_lng, place_id, maps_url, photo_url
            
        print(f"Could not find location: {place_name} in {location}")
        return False, None, None, None, None, None
    except Exception as e:
        print(f"Error validating coordinates with Google Maps: {str(e)}")
        return False, None, None, None, None, None

def get_places_from_ai(prompt):
    """Get place recommendations and their coordinates using OpenAI."""
    # First, extract the target location
    location = extract_location_from_prompt(prompt)
    if not location:
        return None
    
    print(f"\n--- Getting recommendations for location: {location} ---")
    system_prompt = f"""You are a travel expert specializing in accurate location recommendations worldwide. For a query about {location}:

    1. Recommend only places that actually exist in {location}
    2. For each place:
       - Provide the EXACT official name of the place as it appears on Google Maps
       - Focus on well-known, easily findable locations
       - Include famous landmarks, attractions, or historically significant places
       - Make sure to use the full official name with location (e.g., "Statue of Liberty National Monument, Liberty Island, New York Harbor")
    3. Write engaging descriptions that highlight unique features
    
    Respond with a JSON array containing exactly the number of places requested.
    Format: [{{
        "name": "Full Official Place Name with Location",
        "description": "Description (2-3 sentences about history, significance, or attractions)",
        "latitude": 0,
        "longitude": 0
    }}, ...]
    
    Note: You can set latitude and longitude to 0 as they will be automatically populated with accurate coordinates."""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        # Parse the JSON response
        content = response.choices[0].message.content
        print(f"\nRaw API Response:\n{content}")
        
        places = json.loads(content)
        print(f"\nParsed Places Data:\n{json.dumps(places, indent=2)}")
        
        # Validate and update coordinates using Google Maps
        validated_places = []
        for place in places:
            is_valid, google_lat, google_lng, place_id, maps_url, photo_url = validate_place_with_google_maps(place['name'], location)
            if is_valid:
                place['latitude'] = google_lat
                place['longitude'] = google_lng
                place['place_id'] = place_id
                place['maps_url'] = maps_url
                place['photo_url'] = photo_url
                validated_places.append(place)
                print(f"✅ Validated and updated coordinates for: {place['name']}")
            else:
                print(f"❌ Could not validate coordinates for: {place['name']}")
                st.warning(f"⚠️ Skipped '{place['name']}' due to invalid coordinates. Please try again.")
        
        print(f"\nFinal validated places count: {len(validated_places)}")
        return validated_places if validated_places else None
    except Exception as e:
        st.error(f"Error getting recommendations: {str(e)}")
        print(f"Error in get_places_from_ai: {str(e)}")
        return None

def create_google_maps_embed(places):
    """Create a Google Maps embed URL with markers for all places."""
    if not places or len(places) == 0:
        print("No places provided for map embed creation")
        return None

    print(f"\n--- Creating map embed for {len(places)} places ---")
    
    # Create the base URL for search mode
    base_url = "https://www.google.com/maps/embed/v1/place"
    
    # Use the first place's place_id for centering the map
    first_place = places[0]
    
    # Add markers for all places
    markers = []
    for i, place in enumerate(places, 1):
        marker = f"&markers=color:red|label:{i}|{place['latitude']},{place['longitude']}"
        markers.append(marker)
        print(f"Added marker {i} for: {place['name']}")
    
    # Construct the final URL with markers
    map_url = f"{base_url}?key={GOOGLE_MAPS_API_KEY}&q=place_id:{first_place['place_id']}&zoom=12{''.join(markers)}"
    print("Map URL created successfully")
    
    return map_url

def create_individual_map_embed(place):
    """Create a Google Maps embed URL for a single place."""
    base_url = "https://www.google.com/maps/embed/v1/view"
    map_url = f"{base_url}?key={GOOGLE_MAPS_API_KEY}&center={place['latitude']},{place['longitude']}&zoom=16"
    return map_url

def main():
    st.title("🌍 AI Trip Planner")
    st.write("Get personalized travel recommendations!")
    
    # User input
    user_prompt = st.text_area(
        "What would you like to know about your destination?",
        placeholder="Example: Tell me 3 places I should visit in Paris, France" +
                   "\nOr: Recommend 5 must-see attractions in Tokyo, Japan" +
                   "\nOr: What are the top 3 historical sites in Rome, Italy?",
        height=100
    )
    
    if st.button("Get Recommendations"):
        if user_prompt:
            with st.spinner("Getting recommendations..."):
                # Get place recommendations
                places = get_places_from_ai(user_prompt)
                
                if places:
                    # Display recommendations
                    st.subheader("Recommended Places")
                    for i, place in enumerate(places, 1):
                        st.markdown(f"### {i}. {place['name']}")
                        
                        # Display location image if available
                        if place.get('photo_url'):
                            st.image(place['photo_url'], caption=place['name'], use_container_width=True)
                        
                        st.write(place['description'])
                        
                        # Create and display individual map
                        map_url = create_individual_map_embed(place)
                        st.components.v1.iframe(
                            map_url,
                            height=300,  # Smaller height for individual maps
                            scrolling=True
                        )
                        
                        st.write(f"📍 [View on Google Maps]({place['maps_url']})")
                        st.write("---")
                        
                    # Add a combined map view link
                    locations = [f"{p['name']}@{p['latitude']},{p['longitude']}" for p in places]
                    combined_map_link = f"https://www.google.com/maps/dir/{'/'.join(urllib.parse.quote(loc) for loc in locations)}"
                    st.write(f"[📍 View all locations on Google Maps]({combined_map_link})")
        else:
            st.warning("Please enter a prompt to get recommendations.")

if __name__ == "__main__":
    main()
