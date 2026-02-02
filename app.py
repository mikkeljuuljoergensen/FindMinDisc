import streamlit as st
import re
import json
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_openai import ChatOpenAI
from retailers import get_product_links
from flight_chart import generate_flight_path, get_flight_stats, FLIGHT_NUMBER_GUIDE, calculate_arm_speed_factor

# --- CONFIGURATION ---
st.set_page_config(page_title="FindMinDisc", page_icon="🥏")


def parse_flight_chart_request(prompt):
    """
    Parse natural language requests for flight charts.
    
    Examples:
    - "Vis mig flight charts for Destroyer, Mamba, Juggernaut og Zone SS, hvis min maks kastelængde er 137 meter"
    - "Sammenlign Buzzz og Roc3 ved 70m kast"
    - "Flight chart for Firebird"
    - "Destroyer vs Wraith"
    - "Tilføj Wraith" (adds to existing)
    - "Også Firebird" (adds to existing)
    
    Returns dict with 'discs' list and 'distance' (or None if not a flight chart request)
    """
    prompt_lower = prompt.lower()
    
    # Check if this is a flight chart request
    flight_keywords = ['flight chart', 'flightchart', 'sammenlign', 'compare', 'vis mig', 'show me', 'chart for', ' vs ', ' mod ']
    is_chart_request = any(kw in prompt_lower for kw in flight_keywords)
    
    # Check if this is an "add to existing" request
    add_keywords = ['tilføj', 'også', 'add', 'inkluder', 'med', 'plus', 'og også', 'hvad med']
    is_add_request = any(kw in prompt_lower for kw in add_keywords)
    
    # Find disc names - use word boundary matching to avoid partial matches
    # Sort by length (longest first) to prefer "Zone SS" over "Zone"
    disc_names_sorted = sorted(DISC_DATABASE.keys(), key=len, reverse=True)
    
    disc_names_found = []
    prompt_remaining = prompt_lower  # Track what's left to match
    
    for disc_name in disc_names_sorted:
        disc_lower = disc_name.lower()
        # Use word boundary matching to avoid "Ra" matching in "Wraith"
        pattern = r'(?:^|[^a-zæøå0-9])' + re.escape(disc_lower) + r'(?:[^a-zæøå0-9]|$)'
        if re.search(pattern, prompt_remaining):
            disc_names_found.append(disc_name)
            prompt_remaining = re.sub(pattern, ' ', prompt_remaining, count=1)
    
    # If multiple discs mentioned, or add request with disc, or chart request with disc
    if len(disc_names_found) >= 2 or (is_chart_request and disc_names_found) or (is_add_request and disc_names_found):
        # Extract distance
        distance = None
        
        # Match "137 meter", "137m", "kaster 137", "kastelængde 137"
        dist_patterns = [
            r'(\d+)\s*(?:meter|m\b)',
            r'kastelængde[^\d]*(\d+)',
            r'kaster[^\d]*(\d+)',
            r'distance[^\d]*(\d+)',
            r'(\d+)\s*(?:ft|feet|fod)',  # feet
        ]
        
        for pattern in dist_patterns:
            match = re.search(pattern, prompt_lower)
            if match:
                distance = int(match.group(1))
                # Convert feet to meters if needed
                if 'ft' in prompt_lower or 'feet' in prompt_lower or 'fod' in prompt_lower:
                    distance = int(distance * 0.3048)
                # Sanity check - if > 200, probably feet
                if distance > 200:
                    distance = int(distance * 0.3048)
                break
        
        return {
            'discs': disc_names_found,
            'distance': distance,  # None means use last_distance
            'is_chart_request': True,
            'is_add_request': is_add_request
        }
    
    return {'is_chart_request': False}


def interpolate_flight_path(path_slow, path_normal, path_fast, arm_factor, user_distance_m):
    """
    Interpolate between slow/normal/fast flight paths based on arm_factor.
    
    arm_factor: 0.0 = slow, 0.5 = normal, 1.0 = fast
    
    Then scale to user's actual throwing distance.
    """
    # Determine which paths to interpolate between
    if arm_factor <= 0.5:
        # Between slow and normal
        t = arm_factor * 2  # 0 to 1
        path_a, path_b = path_slow, path_normal
    else:
        # Between normal and fast
        t = (arm_factor - 0.5) * 2  # 0 to 1
        path_a, path_b = path_normal, path_fast
    
    # Get max distances from paths
    max_dist_a = path_a[-1]['y'] if path_a else 400
    max_dist_b = path_b[-1]['y'] if path_b else 400
    
    # Interpolate max distance
    interpolated_max_dist = max_dist_a + t * (max_dist_b - max_dist_a)
    
    # Scale factor to match user's distance
    user_distance_ft = user_distance_m / 0.3048
    scale = user_distance_ft / interpolated_max_dist if interpolated_max_dist > 0 else 1.0
    
    # Interpolate points and scale to user distance
    result = []
    for i in range(min(len(path_a), len(path_b))):
        x_a, y_a = path_a[i]['x'], path_a[i]['y']
        x_b, y_b = path_b[i]['x'], path_b[i]['y']
        
        # Interpolate x (turn/fade) based on arm factor
        x = x_a + t * (x_b - x_a)
        # Scale y to user's distance
        y = (y_a + t * (y_b - y_a)) * scale
        
        result.append({'x': x, 'y': y})
    
    return result


def calculate_power_percentage(user_distance_m, speed, glide):
    """
    Calculate power percentage: how well user's distance matches disc requirements.
    
    Uses the practical "speed × 10" rule that disc golfers commonly use:
    - Speed 4 putter: needs ~40m arm
    - Speed 7 fairway: needs ~70m arm
    - Speed 12 driver: needs ~120m arm
    
    Glide adds a small bonus (~2m per glide point).
    
    Returns percentage where 100% = you can throw this disc properly.
    """
    # Practical expected distance: speed * 10 + glide * 2
    # This matches what disc golfers actually experience
    expected_m = speed * 10 + glide * 2
    
    # Power percentage
    power_pct = (user_distance_m / expected_m) * 100
    
    return {
        'power_pct': power_pct,
        'expected_m': expected_m,
        'ratio': user_distance_m / expected_m
    }


def render_flight_chart_comparison(disc_names, throwing_distance):
    """Render a flight chart comparison for specified discs using actual database paths."""
    import pandas as pd
    
    st.markdown(f"### 🥏 Flight Chart Sammenligning")
    st.markdown(f"*Din kastelængde: **{throwing_distance}m***")
    
    # Collect disc data from FULL database with flight paths
    discs_with_data = []
    not_found = []
    
    for disc_name in disc_names:
        # Try to find the disc in FULL database (case-insensitive)
        disc_data = None
        matched_name = None
        for db_name, db_data in DISC_DATABASE_FULL.items():
            if db_name.lower() == disc_name.lower():
                disc_data = db_data
                matched_name = db_name
                break
        
        if disc_data and disc_data.get('flight_path_bh_normal'):
            discs_with_data.append({
                'name': matched_name,
                'speed': disc_data.get('speed', 5),
                'glide': disc_data.get('glide', 4),
                'turn': disc_data.get('turn', 0),
                'fade': disc_data.get('fade', 2),
                'manufacturer': disc_data.get('manufacturer', 'Ukendt'),
                'path_slow': disc_data.get('flight_path_bh_slow', []),
                'path_normal': disc_data.get('flight_path_bh_normal', []),
                'path_fast': disc_data.get('flight_path_bh_fast', [])
            })
        else:
            not_found.append(disc_name)
    
    if not_found:
        st.warning(f"Kunne ikke finde flight data for: {', '.join(not_found)}")
    
    if not discs_with_data:
        st.error("Ingen af de angivne discs blev fundet i databasen med flight paths.")
        return
    
    # Calculate arm factor and interpolate paths
    all_data = []
    stats_data = []
    
    for disc in discs_with_data:
        # Calculate power/arm factor
        power_info = calculate_power_percentage(throwing_distance, disc['speed'], disc['glide'])
        
        # Map ratio to arm factor (0.0 = slow, 0.5 = normal, 1.0 = fast)
        ratio = power_info['ratio']
        if ratio <= 0.894:
            arm_factor = 0.0
        elif ratio <= 1.0:
            arm_factor = 0.5 * (ratio - 0.894) / (1.0 - 0.894)
        elif ratio <= 1.053:
            arm_factor = 0.5 + 0.5 * (ratio - 1.0) / (1.053 - 1.0)
        else:
            arm_factor = min(1.0, 0.5 + 0.5 * (ratio - 1.0) / 0.053)
        
        # Interpolate flight path based on arm factor
        path = interpolate_flight_path(
            disc['path_slow'], disc['path_normal'], disc['path_fast'],
            arm_factor, throwing_distance
        )
        
        # Get stats from interpolated path
        max_turn = min(p['x'] for p in path) if path else 0
        final_x = path[-1]['x'] if path else 0
        fade_amount = final_x - max_turn
        
        stats_data.append({
            'name': disc['name'],
            'manufacturer': disc['manufacturer'],
            'speed': disc['speed'],
            'glide': disc['glide'],
            'turn': disc['turn'],
            'fade': disc['fade'],
            'flight_numbers': f"{disc['speed']}/{disc['glide']}/{disc['turn']}/{disc['fade']}",
            'power_pct': power_info['power_pct'],
            'expected_m': power_info['expected_m'],
            'max_turn': max_turn,
            'fade_amount': fade_amount,
            'arm_factor': arm_factor
        })
        
        # Add to chart data - convert to meters
        disc_label = f"{disc['name']} ({disc['speed']}/{disc['glide']}/{disc['turn']}/{disc['fade']})"
        for p in path:
            all_data.append({
                'Disc': disc_label,
                'Turn/Fade (m)': round(p['x'] * 0.3048, 2),  # Convert feet to meters
                'Distance (m)': round(p['y'] * 0.3048, 1)
            })
    
    # Create chart
    df = pd.DataFrame(all_data)
    
    # Use Altair for vertical flight chart (like dgputtheads)
    try:
        import altair as alt
        
        chart = alt.Chart(df).mark_line(strokeWidth=3).encode(
            x=alt.X('Turn/Fade (m):Q', 
                    title='Turn/Fade (meter)',
                    scale=alt.Scale(domain=[-2, 2])),
            y=alt.Y('Distance (m):Q', 
                    title='Distance (meter)',
                    scale=alt.Scale(domain=[0, throwing_distance + 10])),
            color=alt.Color('Disc:N', legend=alt.Legend(orient='bottom')),
            tooltip=['Disc', 'Distance (m)', 'Turn/Fade (m)']
        ).properties(
            height=500,
            title=f'Flight Paths ved {throwing_distance}m kastelængde'
        ).configure_axis(
            grid=True
        )
        
        st.altair_chart(chart, use_container_width=True)
        
    except ImportError:
        # Fallback to line_chart if altair not available
        pivot_df = df.pivot(index='Distance (m)', columns='Disc', values='Turn/Fade (m)')
        st.line_chart(pivot_df, height=500)
    
    # Show detailed stats for each disc
    st.markdown("### 📊 Disc Detaljer")
    
    for stat in stats_data:
        power_pct = stat['power_pct']
        
        with st.expander(f"**{stat['manufacturer']} {stat['name']}** ({stat['flight_numbers']})", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if power_pct >= 95:
                    st.metric("Din power", f"🚀 {power_pct:.0f}%", 
                              help="Du kan kaste denne disc med fuld power")
                elif power_pct >= 70:
                    st.metric("Din power", f"✅ {power_pct:.0f}%",
                              help="God match for din kastelængde")
                elif power_pct >= 50:
                    st.metric("Din power", f"⚠️ {power_pct:.0f}%",
                              help="Denne disc kræver mere armhastighed")
                else:
                    st.metric("Din power", f"❌ {power_pct:.0f}%",
                              help="Denne disc er for hurtig til din kastelængde")
            
            with col2:
                st.metric("Kræver arm", f"{stat['expected_m']:.0f}m",
                          help="Kastelængde for at udnytte discen fuldt (speed×10 + glide×2)")
            
            with col3:
                turn = stat['turn']
                fade = stat['fade']
                if turn <= -3:
                    stability = "Meget understabil ↪️"
                elif turn <= -1:
                    stability = "Understabil ↪️"
                elif fade >= 3:
                    stability = "Meget overstabil ↩️"
                elif fade >= 2:
                    stability = "Overstabil ↩️"
                else:
                    stability = "Stabil →"
                st.metric("Stabilitet", stability)
    
    return True

# --- LOAD DISC DATABASE ---
# Flight data from https://flightcharts.dgputtheads.com/
@st.cache_data
def load_disc_database():
    try:
        with open("disc_database.json", "r") as f:
            return json.load(f)
    except:
        return {}

@st.cache_data
def load_disc_database_full():
    """Load full database with flight paths."""
    try:
        with open("disc_database_full.json", "r") as f:
            return json.load(f)
    except:
        return {}

DISC_DATABASE = load_disc_database()
DISC_DATABASE_FULL = load_disc_database_full()

def render_flight_chart(disc_name, speed, glide, turn, fade, arm_speed='normal', user_distance_m=None):
    """Render a flight chart using Streamlit's native chart."""
    import pandas as pd
    
    # Use continuous calculation if distance is provided
    if user_distance_m is not None:
        path = generate_flight_path(speed, glide, turn, fade, user_distance_m=user_distance_m)
        stats = get_flight_stats(speed, glide, turn, fade, user_distance_m=user_distance_m)
        factors = calculate_arm_speed_factor(user_distance_m, speed, glide)
    else:
        path = generate_flight_path(speed, glide, turn, fade, arm_speed)
        stats = get_flight_stats(speed, glide, turn, fade, arm_speed)
        factors = None
    
    # Convert feet to meters for y-axis
    df = pd.DataFrame([
        {'Fade/Turn': p['x'], 'Distance (m)': round(p['y'] * 0.3048, 1)} 
        for p in path
    ])
    
    # Create the chart
    st.markdown(f"**{disc_name}** ({speed}/{glide}/{turn}/{fade})")
    
    # Use columns for layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Plot using st.line_chart with x and y swapped for vertical flight path
        st.line_chart(
            df,
            x='Fade/Turn',
            y='Distance (m)',
            height=300
        )
    
    with col2:
        if factors:
            arm_pct = int(factors['arm_factor'] * 100)
            if arm_pct >= 100:
                st.metric("Din power", f"🚀 {arm_pct}%")
            elif arm_pct >= 75:
                st.metric("Din power", f"✅ {arm_pct}%")
            else:
                st.metric("Din power", f"⚠️ {arm_pct}%")
            st.caption(f"Optimal: {factors['expected_dist_m']:.0f}m")
        st.metric("Max distance", f"{stats['max_distance_m']}m")
        st.metric("Max turn", f"{stats['max_turn']:.2f}")
        st.metric("Fade", f"{stats['fade_amount']:.2f}")

def render_comparison_chart(discs_data, arm_speed='normal'):
    """Render comparison chart for multiple discs."""
    import pandas as pd
    
    all_data = []
    for disc in discs_data:
        name = disc['name']
        path = generate_flight_path(
            disc['speed'], disc['glide'], disc['turn'], disc['fade'], 
            arm_speed
        )
        for p in path:
            all_data.append({
                'Disc': name,
                'Fade/Turn': p['x'],
                'Distance (m)': round(p['y'] * 0.3048, 1)
            })
    
    df = pd.DataFrame(all_data)
    
    # Pivot for multi-line chart
    pivot_df = df.pivot(index='Distance (m)', columns='Disc', values='Fade/Turn')
    
    st.line_chart(pivot_df, height=400)

def render_recommendation_flight_charts(disc_names, throwing_distance, database):
    """Render flight charts for recommended discs based on user's throwing distance."""
    import pandas as pd
    
    st.markdown(f"### 📈 Flight Charts (din kastelængde: {throwing_distance}m)")
    
    # Collect disc data
    discs_with_data = []
    for disc_name in disc_names:
        # Try to find the disc in database (case-insensitive)
        disc_data = None
        for db_name, db_data in database.items():
            if db_name.lower() == disc_name.lower():
                disc_data = db_data
                disc_name = db_name  # Use correct casing
                break
        
        if disc_data and disc_data.get('speed'):
            discs_with_data.append({
                'name': disc_name,
                'speed': disc_data.get('speed', 5),
                'glide': disc_data.get('glide', 4),
                'turn': disc_data.get('turn', 0),
                'fade': disc_data.get('fade', 2),
                'manufacturer': disc_data.get('manufacturer', 'Ukendt')
            })
    
    if not discs_with_data:
        return
    
    # Generate paths for all discs using precise calculation
    all_data = []
    stats_data = []
    
    for disc in discs_with_data:
        # Use user_distance_m for precise calculation
        path = generate_flight_path(
            disc['speed'], disc['glide'], disc['turn'], disc['fade'], 
            user_distance_m=throwing_distance
        )
        stats = get_flight_stats(
            disc['speed'], disc['glide'], disc['turn'], disc['fade'], 
            user_distance_m=throwing_distance
        )
        
        # Calculate arm speed factor for this specific disc
        factors = calculate_arm_speed_factor(throwing_distance, disc['speed'], disc['glide'])
        
        stats_data.append({
            'name': disc['name'],
            'distance': stats['max_distance_m'],
            'turn': stats['max_turn'],
            'fade': stats['fade_amount'],
            'arm_factor': factors['arm_factor'],
            'expected_dist': factors['expected_dist_m']
        })
        
        for p in path:
            all_data.append({
                'Disc': f"{disc['name']} ({disc['speed']}/{disc['glide']}/{disc['turn']}/{disc['fade']})",
                'Turn/Fade': p['x'],
                'Distance (m)': round(p['y'] * 0.3048, 1)
            })
    
    df = pd.DataFrame(all_data)
    
    # Create pivot table for comparison chart
    pivot_df = df.pivot(index='Distance (m)', columns='Disc', values='Turn/Fade')
    
    # Show the chart
    st.line_chart(pivot_df, height=350)
    
    # Show stats table
    st.markdown("**Sammenligning:**")
    cols = st.columns(len(stats_data))
    for i, stat in enumerate(stats_data):
        with cols[i]:
            st.markdown(f"**{stat['name']}**")
            # Show arm factor as percentage
            arm_pct = int(stat['arm_factor'] * 100)
            if arm_pct >= 100:
                arm_emoji = "🚀"
                arm_text = f"{arm_pct}% power"
            elif arm_pct >= 75:
                arm_emoji = "✅"
                arm_text = f"{arm_pct}% power"
            else:
                arm_emoji = "⚠️"
                arm_text = f"Kun {arm_pct}%"
            st.caption(f"{arm_emoji} {arm_text}")
            st.caption(f"📏 Forventet: {stat['expected_dist']:.0f}m")
            st.caption(f"↪️ Turn: {stat['turn']:.2f}")
            st.caption(f"↩️ Fade: {stat['fade']:.2f}")

def get_disc_recommendations_by_distance(max_dist, disc_type, flight_pref, brand=None):
    """Get disc recommendations based on throwing distance and preferences."""
    recommendations = []
    
    # Map disc type to speed range
    speed_ranges = {
        "Putter": (1, 3),
        "Midrange": (4, 6),
        "Fairway driver": (7, 9),
        "Distance driver": (10, 14)
    }
    min_speed, max_speed = speed_ranges.get(disc_type, (1, 14))
    
    # Adjust max speed based on throwing distance
    # Rule of thumb: You need ~10m per speed rating to throw a disc properly
    recommended_max_speed = max_dist // 10
    actual_max_speed = min(max_speed, recommended_max_speed)
    
    for name, data in DISC_DATABASE.items():
        speed = data.get("speed", 0)
        turn = data.get("turn", 0)
        fade = data.get("fade", 0)
        manufacturer = data.get("manufacturer", "").lower()
        
        # Check if speed is in range for disc type
        if not (min_speed <= speed <= max_speed):
            continue
        
        # Filter by brand if specified
        if brand and brand.lower() not in manufacturer:
            continue
        
        # Filter by flight preference
        if flight_pref == "Understabil" and turn >= 0:
            continue
        elif flight_pref == "Overstabil" and turn < 0:
            continue
        elif flight_pref == "Lige/stabil" and (turn < -2 or fade > 2):
            continue
        
        # Prioritize discs that match throwing distance
        priority = 0
        if speed <= recommended_max_speed:
            priority = 10  # Good match
        elif speed <= recommended_max_speed + 2:
            priority = 5   # Acceptable with lightweight
        else:
            priority = 1   # Not ideal
        
        # Boost understable discs for beginners (under 70m)
        if max_dist < 70 and turn <= -2:
            priority += 5
        
        recommendations.append({
            "name": name,
            "data": data,
            "priority": priority
        })
    
    # Sort by priority
    recommendations.sort(key=lambda x: x["priority"], reverse=True)
    return recommendations[:15]  # Return top 15 matches

def format_filtered_discs_for_ai(max_dist, disc_type, flight_pref, brand=None):
    """Format only relevant discs for AI context based on user preferences."""
    recommendations = get_disc_recommendations_by_distance(max_dist, disc_type, flight_pref, brand)
    
    if not recommendations:
        # Fallback: just get any discs of that type
        speed_ranges = {
            "Putter": (1, 3),
            "Midrange": (4, 6),
            "Fairway driver": (7, 9),
            "Distance driver": (10, 14)
        }
        min_speed, max_speed = speed_ranges.get(disc_type, (1, 14))
        
        for name, data in list(DISC_DATABASE.items())[:50]:
            speed = data.get("speed", 0)
            if min_speed <= speed <= max_speed:
                recommendations.append({"name": name, "data": data})
            if len(recommendations) >= 15:
                break
    
    lines = [f"ANBEFALEDE DISCS TIL DIG (baseret på {max_dist}m kast, {disc_type}, {flight_pref}):"]
    for rec in recommendations:
        name = rec["name"]
        data = rec["data"]
        line = f"  • {name} ({data.get('manufacturer', '?')}): Speed {data.get('speed')}, Glide {data.get('glide')}, Turn {data.get('turn')}, Fade {data.get('fade')}"
        lines.append(line)
    
    return "\n".join(lines)

# --- PLASTIC KNOWLEDGE BASE ---
# Source: https://flightcharts.dgputtheads.com/discgolfplastics.html
PLASTIC_GUIDE = """
PLASTIK GUIDE (fra holdbar/overstabil til blød/understabil):

**Innova:**
- Champion/Halo Star: Mest holdbar, overstabil, glat
- Star: Holdbar, godt greb, let overstabil
- GStar: Fleksibel, godt greb, mere understabil
- Pro: Medium holdbar, godt greb
- DX: Billig, blødt, slides hurtigt understabilt

**Discraft:**
- Z/Titanium: Mest holdbar, overstabil, glat
- ESP: Holdbar, fantastisk greb
- ESP FLX/Z FLX: Fleksibel version
- X/Jawbreaker: Medium, godt greb
- Pro D: Billig base plastik

**Latitude 64/Dynamic Discs/Westside (Trilogy):**
- Opto/Lucid/VIP: Mest holdbar, overstabil
- Gold Line/Fuzion/Tournament: Holdbar, godt greb
- Frost/Fluid/Elasto: Fleksibel
- Retro/Prime/Origio: Base plastik

**MVP/Axiom/Streamline:**
- Proton: Mest holdbar, overstabil, glat
- Neutron: Holdbar, fantastisk greb
- Plasma: Holdbar med swirl
- Fission: Let, god til begyndere
- Electron: Base plastik til putters

**Discmania:**
- C Line = Innova Champion
- S Line = Innova Star
- P Line = Innova Pro
- D Line = Innova DX

**Kastaplast:**
- K1: Premium holdbar
- K2: Fleksibel premium
- K3: Base plastik

**Generelle råd:**
- Begyndere: Start med base plastik (DX, Pro D, Retro) - billigt og lærer dig at kaste
- Erfarne: Premium plastik (Star, ESP, Neutron) - holder formen længere
- Koldt vejr: Fleksibelt plastik (GStar, FLX, Frost)
- Greb i regn: ESP, Neutron, Star
"""

# --- API KEY HANDLING ---
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    st.error("Mangler OPENAI_API_KEY. Tilføj den til Streamlit Secrets.")
    st.stop()

# --- AI SETUP ---
llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=api_key,
    temperature=0.7
)
search = DuckDuckGoSearchRun()

# --- INITIALIZE SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "step" not in st.session_state:
    st.session_state.step = "start"
if "user_prefs" not in st.session_state:
    st.session_state.user_prefs = {}
if "shown_discs" not in st.session_state:
    st.session_state.shown_discs = []  # Remember discs shown in flight charts
if "last_distance" not in st.session_state:
    st.session_state.last_distance = 80  # Remember last used distance

# --- HEADER ---
st.header("FindMinDisc 🥏")

# --- HELPER FUNCTIONS ---
def add_bot_message(content):
    st.session_state.messages.append({"role": "assistant", "content": content})

def add_user_message(content):
    st.session_state.messages.append({"role": "user", "content": content})

def reset_conversation():
    st.session_state.messages = []
    st.session_state.step = "start"
    st.session_state.user_prefs = {}
    st.session_state.shown_discs = []
    st.session_state.last_distance = 80

# --- START CONVERSATION ---
if st.session_state.step == "start":
    add_bot_message("""Hej! Jeg hjælper dig med at finde den perfekte disc 🥏

**Vælg en mulighed:**
1️⃣ Putter
2️⃣ Midrange
3️⃣ Fairway driver
4️⃣ Distance driver

**Eller spørg mig direkte:**
*"Vis flight charts for Destroyer, Mamba og Zone SS ved 100m kast"*
*"Sammenlign Buzzz og Roc3"*
*"Hvilken disc til skovbaner?"*""")
    st.session_state.step = "ask_type"

# --- DISPLAY MESSAGES ---
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# --- CHAT INPUT ---
if prompt := st.chat_input("Skriv dit svar..."):
    add_user_message(prompt)
    st.chat_message("user").write(prompt)
    
    with st.chat_message("assistant"):
        
        # --- FIRST: Check for natural language flight chart requests ---
        chart_request = parse_flight_chart_request(prompt)
        
        if chart_request.get('is_chart_request'):
            # User asked for flight chart comparison
            new_discs = chart_request['discs']
            is_add = chart_request.get('is_add_request', False)
            
            # Determine distance: use provided, or fall back to last used
            distance = chart_request.get('distance')
            if distance is None:
                distance = st.session_state.last_distance
            
            # If adding to existing, combine with previous discs
            if is_add and st.session_state.shown_discs:
                # Add new discs to existing list (avoid duplicates)
                all_discs = list(st.session_state.shown_discs)
                for disc in new_discs:
                    if disc not in all_discs:
                        all_discs.append(disc)
                reply = f"Tilføjet **{', '.join(new_discs)}** - viser nu **{len(all_discs)} discs** ved {distance}m:"
            else:
                # New chart request - replace previous
                all_discs = new_discs
                reply = f"Her er flight charts for **{', '.join(all_discs)}** ved din kastelængde på **{distance}m**:"
            
            st.markdown(reply)
            add_bot_message(reply)
            
            # Render the comparison chart
            render_flight_chart_comparison(all_discs, distance)
            
            # Update session state
            st.session_state.step = "done"
            st.session_state.user_prefs["max_dist"] = distance
            st.session_state.shown_discs = all_discs  # Remember shown discs
            st.session_state.last_distance = distance  # Remember distance
            
            follow_up = "\n\n💬 Du kan tilføje flere - f.eks. 'Også Wraith' eller 'Tilføj Firebird'"
            st.markdown(follow_up)
            add_bot_message(follow_up)
        
        # --- STEP: ASK DISC TYPE ---
        elif st.session_state.step == "ask_type":
            prompt_lower = prompt.lower()
            if "1" in prompt or "putter" in prompt_lower:
                st.session_state.user_prefs["disc_type"] = "Putter"
            elif "2" in prompt or "midrange" in prompt_lower or "mid" in prompt_lower:
                st.session_state.user_prefs["disc_type"] = "Midrange"
            elif "3" in prompt or "fairway" in prompt_lower:
                st.session_state.user_prefs["disc_type"] = "Fairway driver"
            elif "4" in prompt or "distance" in prompt_lower or "driver" in prompt_lower:
                st.session_state.user_prefs["disc_type"] = "Distance driver"
            else:
                reply = "Hmm, jeg forstod ikke helt. Skriv 1, 2, 3 eller 4 - eller skriv disc-typen (f.eks. 'putter' eller 'midrange')"
                st.write(reply)
                add_bot_message(reply)
                st.rerun()
            
            reply = f"Fedt, du leder efter en **{st.session_state.user_prefs['disc_type']}**!\n\nHvor langt kaster du cirka? (i meter)"
            st.write(reply)
            add_bot_message(reply)
            st.session_state.step = "ask_distance"
        
        # --- STEP: ASK DISTANCE ---
        elif st.session_state.step == "ask_distance":
            numbers = re.findall(r'\d+', prompt)
            if numbers:
                dist = int(numbers[0])
                if dist > 200:
                    dist = int(dist * 0.3)
                st.session_state.user_prefs["max_dist"] = dist
                
                reply = f"Okay, du kaster ca. **{dist}m**.\n\nHvilken flyvning ønsker du?\n\n1️⃣ Lige/stabil\n2️⃣ Understabil (drejer til højre for højrehåndede)\n3️⃣ Overstabil (drejer til venstre for højrehåndede)\n4️⃣ Ved ikke"
                st.write(reply)
                add_bot_message(reply)
                st.session_state.step = "ask_flight"
            else:
                reply = "Jeg fangede ikke et tal. Hvor mange meter kaster du cirka? (f.eks. '60' eller '80 meter')"
                st.write(reply)
                add_bot_message(reply)
        
        # --- STEP: ASK FLIGHT ---
        elif st.session_state.step == "ask_flight":
            prompt_lower = prompt.lower()
            if "1" in prompt or "lige" in prompt_lower or "stabil" in prompt_lower:
                st.session_state.user_prefs["flight"] = "Lige/stabil"
            elif "2" in prompt or "understabil" in prompt_lower or "højre" in prompt_lower:
                st.session_state.user_prefs["flight"] = "Understabil"
            elif "3" in prompt or "overstabil" in prompt_lower or "venstre" in prompt_lower:
                st.session_state.user_prefs["flight"] = "Overstabil"
            elif "4" in prompt or "ved ikke" in prompt_lower:
                st.session_state.user_prefs["flight"] = "Ved ikke"
            else:
                reply = "Skriv 1, 2, 3 eller 4 - eller beskriv flyvningen (f.eks. 'lige' eller 'understabil')"
                st.write(reply)
                add_bot_message(reply)
                st.rerun()
            
            reply = "Godt! Er der andet jeg skal vide? (f.eks. 'god i vind', 'til putting', 'til skov', eller bare skriv 'nej')"
            st.write(reply)
            add_bot_message(reply)
            st.session_state.step = "ask_extra"
        
        # --- STEP: ASK EXTRA INFO ---
        elif st.session_state.step == "ask_extra":
            extra = prompt if prompt.lower() not in ["nej", "nej tak", "ingen", "-"] else ""
            st.session_state.user_prefs["extra"] = extra
            
            prefs = st.session_state.user_prefs
            disc_type = prefs["disc_type"]
            max_dist = prefs["max_dist"]
            flight = prefs["flight"]
            extra_info = prefs.get("extra", "")
            
            # Check for mismatch and warn user BEFORE searching
            mismatch_warning = ""
            if max_dist < 60 and disc_type == "Distance driver":
                mismatch_warning = f"""⚠️ **Vent lige lidt!**

Du kaster {max_dist}m og leder efter en distance driver. Det er typisk ikke det bedste valg:
- Distance drivers (speed 10+) kræver **80+ meter armhastighed** for at flyve korrekt
- Med {max_dist}m vil en distance driver sandsynligvis bare dykke ned eller fade hårdt til venstre

**Jeg anbefaler i stedet:**
- **Putter** (speed 1-3) til præcision
- **Midrange** (speed 4-6) til allround brug
- **Fairway driver** (speed 7-9) til lidt mere distance

Men okay, du bad om distance drivers, så her er nogle **letvægts understabile** modeller der kan virke:

---

"""
            elif max_dist < 50 and disc_type == "Fairway driver":
                mismatch_warning = f"""⚠️ **Bemærk:** Med {max_dist}m kastelængde kan en midrange (speed 4-6) måske passe bedre end en fairway driver. Men her er mine anbefalinger:

---

"""
            
            with st.spinner("Søger efter de bedste discs til dig..."):
                search_query = f"best {disc_type} disc golf {flight} {extra_info} review recommendation lightweight beginner"
                try:
                    search_results = search.run(search_query)[:4000]
                except:
                    search_results = ""
                
                speed_ranges = {
                    "Putter": "speed 1-3",
                    "Midrange": "speed 4-6",
                    "Fairway driver": "speed 7-9",
                    "Distance driver": "speed 10-14"
                }
                speed_hint = speed_ranges.get(disc_type, "")
                recommended_max_speed = max(6, min(14, max_dist // 10))
                
                # Warning for AI
                ai_warning = ""
                if max_dist < 60 and disc_type == "Distance driver":
                    ai_warning = f"""KRITISK: Brugeren kaster kun {max_dist}m men vil have distance drivers.
Anbefal KUN letvægts (150-160g) understabile distance drivers.
Forklar at de bør overveje midranges eller fairway drivers i stedet."""
                elif max_dist < 50 and disc_type == "Fairway driver":
                    ai_warning = f"Brugeren kaster {max_dist}m. Anbefal letvægts understabile fairways."
                
                # Handle brand preferences
                brand_instruction = ""
                brand_filter = None
                extra_lower = extra_info.lower() if extra_info else ""
                if "mvp" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt MVP discs. Anbefal KUN MVP discs!"
                    brand_filter = "MVP"
                elif "axiom" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Axiom discs. Anbefal KUN Axiom discs!"
                    brand_filter = "Axiom"
                elif "streamline" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Streamline discs. Anbefal KUN Streamline discs!"
                    brand_filter = "Streamline"
                elif "innova" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Innova discs. Anbefal KUN Innova discs!"
                    brand_filter = "Innova"
                elif "discraft" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Discraft discs. Anbefal KUN Discraft discs!"
                    brand_filter = "Discraft"
                elif "latitude" in extra_lower or "lat64" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Latitude 64 discs. Anbefal KUN Latitude 64 discs!"
                    brand_filter = "Latitude 64"
                elif "discmania" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Discmania discs. Anbefal KUN Discmania discs!"
                    brand_filter = "Discmania"
                elif "kastaplast" in extra_lower:
                    brand_instruction = "VIGTIGT: Brugeren ønsker specifikt Kastaplast discs. Anbefal KUN Kastaplast discs!"
                    brand_filter = "Kastaplast"
                
                # Get filtered disc recommendations from database
                filtered_discs = format_filtered_discs_for_ai(max_dist, disc_type, flight, brand_filter)
                
                ai_prompt = f"""Brugerprofil: kaster {max_dist}m, ønsker {flight} flyvning.
{ai_warning}
{brand_instruction}

Disc-type: **{disc_type}** ({speed_hint})
Ekstra ønsker: {extra_info if extra_info else "Ingen"}

{filtered_discs}

HASTIGHEDS-GUIDE (vigtig!):
- Speed 10+ kræver 80+ meter kastelængde
- Speed 7-9 kræver 60-80 meter kastelængde  
- Speed 4-6 kræver 40-60 meter kastelængde
- Speed 1-3: kan kastes af alle

UNDERSTABIL vs OVERSTABIL:
- Negative turn (f.eks. -3) = understabil = drejer HØJRE for RH-backhand = lettere at kaste langt
- Positiv fade (f.eks. +3) = fader VENSTRE til slut
- Begyndere og kastere under 70m bør vælge understabile discs (turn -2 eller lavere)

Søgeresultater:
{search_results}

Giv 3 FORSKELLIGE {disc_type.lower()}-anbefalinger på dansk.
PRIORITER discs fra databasen ovenfor da de har verificerede flight numbers.
Vær kreativ - anbefal ikke altid de samme discs!

REGLER:
- Anbefal KUN {disc_type}s
- Følg brugerens mærke-præference hvis angivet
- For kastere under 70m: anbefal letvægt (150-165g) og understabile discs
- Nævn vægt i gram
- Hvis valget er dårligt, sig det tydeligt
- VARIER dine anbefalinger - der findes mange gode discs!
- Anbefal IKKE plastik - brugeren kan spørge om hjælp til det bagefter

FORMAT FOR HVER DISC:

### 1. **[DiscNavn]** af [Mærke]
- Flight: X/X/X/X, Vægt: XXXg
- ✅ Fordele: ...
- ❌ Ulemper: ...

Afslut med en kort sammenligning og tilbyd hjælp til valg af plastik."""

                try:
                    ai_response = llm.invoke(ai_prompt).content
                    
                    # Find disc names - look for **Name** pattern
                    bold_matches = re.findall(r'\*\*([A-Za-z0-9\s\-]+)\*\*', ai_response)
                    disc_names = []
                    skip_words = {'flight', 'numbers', 'fordele', 'ulemper', 'plastik', 'sammenligning', 
                                  'disc', 'discs', 'speed', 'glide', 'turn', 'fade', 'premium', 'base', 
                                  'distance', 'driver', 'putter', 'midrange', 'fairway', 'innova', 
                                  'discraft', 'discmania', 'latitude', 'mvp', 'axiom', 'kastaplast', 
                                  'westside', 'dynamic', 'navn', 'mærke', 'af', 'anbefaling', 'vent',
                                  'bemærk', 'lige', 'lidt', 'prodigy', 'lone', 'star', 'streamline',
                                  'thought', 'space', 'clash', 'dga', 'viking', 'yikun', 'gateway'}
                    
                    for match in bold_matches:
                        words = match.strip().split()
                        for word in reversed(words):
                            word_clean = word.strip()
                            if word_clean.lower() not in skip_words and len(word_clean) > 2:
                                if word_clean not in disc_names:
                                    disc_names.append(word_clean)
                                break
                    
                    disc_names = disc_names[:3]
                    
                    # Build buy links for each disc and inject into response
                    modified_response = ai_response
                    for disc in disc_names:
                        if disc and len(disc) > 2:
                            # Get product links from stores
                            links = get_product_links(disc)
                            
                            # Build buy links - only include stores that have the disc
                            buy_link_parts = []
                            if 'Disc Tree' in links:
                                buy_link_parts.append(f"[Disc Tree]({links['Disc Tree']})")
                            if 'NewDisc' in links:
                                buy_link_parts.append(f"[NewDisc]({links['NewDisc']})")
                            
                            if buy_link_parts:
                                buy_links = f"\n   🛒 **Køb:** {' | '.join(buy_link_parts)}"
                                
                                # Find the Ulemper line for this disc and add links after it
                                pattern = rf'(\*\*{re.escape(disc)}\*\*.*?❌ Ulemper:[^\n]*)'
                                match = re.search(pattern, modified_response, re.DOTALL | re.IGNORECASE)
                                if match:
                                    modified_response = modified_response.replace(
                                        match.group(1), 
                                        match.group(1) + buy_links
                                    )
                    
                    # Add warning to response if mismatch
                    final_reply = f"""{mismatch_warning}{modified_response}

---
*Spørg mig om mere, eller skriv 'forfra' for at starte helt forfra.*"""
                    
                    # Store disc names for flight chart
                    st.session_state['recommended_discs'] = disc_names

                except Exception as e:
                    error_str = str(e).lower()
                    if "429" in str(e) or "rate" in error_str:
                        final_reply = "⏳ API'en har brug for en pause. Vent lidt og prøv igen."
                    elif "insufficient_quota" in error_str or "billing" in error_str:
                        final_reply = "💳 Din OpenAI konto mangler credits. Tilføj betalingsmetode på platform.openai.com"
                    elif "invalid_api_key" in error_str or "unauthorized" in error_str:
                        final_reply = "🔑 Ugyldig API-nøgle. Tjek at OPENAI_API_KEY er korrekt i Streamlit Secrets."
                    else:
                        final_reply = f"⚠️ Fejl: {e}"
                
                st.markdown(final_reply)
                add_bot_message(final_reply)
                
                # Show flight charts for recommended discs
                if 'recommended_discs' in st.session_state and st.session_state['recommended_discs']:
                    render_recommendation_flight_charts(
                        st.session_state['recommended_discs'],
                        max_dist,
                        DISC_DATABASE
                    )
                
                st.session_state.step = "done"
        
        # --- STEP: DONE - CONTINUE CONVERSATION ---
        elif st.session_state.step == "done":
            if "forfra" in prompt.lower():
                reset_conversation()
                st.rerun()
            else:
                with st.spinner("Søger nye anbefalinger..."):
                    prefs = st.session_state.user_prefs
                    
                    # Check if user is updating their distance
                    numbers = re.findall(r'\d+', prompt)
                    if numbers:
                        new_dist = int(numbers[0])
                        if new_dist > 200:
                            new_dist = int(new_dist * 0.3)
                        if new_dist < 200:  # Likely a distance update
                            prefs["max_dist"] = new_dist
                    
                    # Check if user is changing disc type
                    prompt_lower = prompt.lower()
                    if "putter" in prompt_lower:
                        prefs["disc_type"] = "Putter"
                    elif "midrange" in prompt_lower or "mid-range" in prompt_lower or "mid range" in prompt_lower:
                        prefs["disc_type"] = "Midrange"
                    elif "fairway" in prompt_lower:
                        prefs["disc_type"] = "Fairway driver"
                    elif "distance" in prompt_lower:
                        prefs["disc_type"] = "Distance driver"
                    
                    # Build context from conversation
                    conversation_context = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in st.session_state.messages[-6:]])
                    
                    # Search again
                    disc_type = prefs.get("disc_type", "disc")
                    max_dist = prefs.get("max_dist", 80)
                    flight = prefs.get("flight", "")
                    
                    search_query = f"best {disc_type} disc golf {flight} {prompt} review"
                    try:
                        search_results = search.run(search_query)[:3000]
                    except:
                        search_results = ""
                    
                    speed_ranges = {
                        "Putter": "speed 1-3",
                        "Midrange": "speed 4-6",
                        "Fairway driver": "speed 7-9",
                        "Distance driver": "speed 10-14"
                    }
                    speed_hint = speed_ranges.get(disc_type, "")
                    
                    warning = ""
                    if max_dist < 70 and disc_type == "Distance driver":
                        warning = f"⚠️ Med {max_dist}m kastelængde anbefales distance drivers IKKE. Foreslå i stedet fairway drivers eller midranges."
                    elif max_dist < 50 and disc_type == "Fairway driver":
                        warning = f"⚠️ Med {max_dist}m kan en midrange være bedre."
                    
                    # Get filtered discs for follow-up
                    filtered_discs = format_filtered_discs_for_ai(max_dist, disc_type, flight, None)
                    
                    follow_up_prompt = f"""Tidligere samtale:
{conversation_context}

Brugerens nuværende profil: kaster {max_dist}m, søger {disc_type}, ønsker {flight} flyvning.
{warning}

Brugerens nye besked: "{prompt}"

{filtered_discs}

HASTIGHEDS-GUIDE:
- Speed 10+ kræver 80+ meter kastelængde
- Speed 7-9 kræver 60-80 meter kastelængde  
- Speed 4-6 kræver 40-60 meter kastelængde
- Speed 1-3: kan kastes af alle

PLASTIK VIDEN (brug kun hvis brugeren spørger om plastik):
{PLASTIC_GUIDE}

REGLER:
- Hvis brugeren ændrer distance eller disc-type, giv NYE anbefalinger
- Hvis brugeren har spørgsmål, svar på dansk
- PRIORITER discs fra databasen ovenfor da de har verificerede flight numbers
- For kastere under 70m: anbefal letvægt (150-165g) og understabile discs
- Hvis disc-typen ikke passer til distancen, SIG DET og foreslå en bedre type
- Hvis brugeren spørger om plastik, brug PLASTIK VIDEN ovenfor til at give præcise råd
- Anbefal IKKE plastik medmindre brugeren spørger

Søgeresultater:
{search_results}

Hvis du giver nye anbefalinger, brug dette format:

### 1. **[DiscNavn]** af [Mærke]
- Flight: X/X/X/X, Vægt: XXXg
- ✅ Fordele: ...
- ❌ Ulemper: ..."""

                    try:
                        reply = llm.invoke(follow_up_prompt).content
                        
                        # Extract disc names for stock links
                        bold_matches = re.findall(r'\*\*([A-Za-z0-9\s\-]+)\*\*', reply)
                        disc_names = []
                        skip_words = {'flight', 'numbers', 'fordele', 'ulemper', 'plastik', 'sammenligning', 
                                      'disc', 'discs', 'speed', 'glide', 'turn', 'fade', 'premium', 'base', 
                                      'distance', 'driver', 'putter', 'midrange', 'fairway', 'innova', 
                                      'discraft', 'discmania', 'latitude', 'mvp', 'axiom', 'kastaplast', 
                                      'westside', 'dynamic', 'navn', 'mærke', 'af', 'anbefaling', 'køb'}
                        
                        for match in bold_matches:
                            words = match.strip().split()
                            for word in reversed(words):
                                word_clean = word.strip()
                                if word_clean.lower() not in skip_words and len(word_clean) > 2:
                                    if word_clean not in disc_names:
                                        disc_names.append(word_clean)
                                    break
                        
                        disc_names = disc_names[:3]
                        
                        # Add buy links after plastic lines
                        modified_reply = reply
                        for disc in disc_names:
                            if disc and len(disc) > 2:
                                links = get_product_links(disc)
                                
                                buy_link_parts = []
                                if 'Disc Tree' in links:
                                    buy_link_parts.append(f"[Disc Tree]({links['Disc Tree']})")
                                if 'NewDisc' in links:
                                    buy_link_parts.append(f"[NewDisc]({links['NewDisc']})")
                                
                                if buy_link_parts:
                                    buy_links = f"\n   🛒 **Køb:** {' | '.join(buy_link_parts)}"
                                    
                                    # Find the Ulemper line for this disc and add links after it
                                    pattern = rf'(\*\*{re.escape(disc)}\*\*.*?❌ Ulemper:[^\n]*)'
                                    match = re.search(pattern, modified_reply, re.DOTALL | re.IGNORECASE)
                                    if match:
                                        modified_reply = modified_reply.replace(
                                            match.group(1), 
                                            match.group(1) + buy_links
                                        )
                        
                        reply = modified_reply
                        
                        # Store disc names for flight chart
                        if disc_names:
                            st.session_state['recommended_discs'] = disc_names
                            
                    except Exception as e:
                        reply = f"Beklager, noget gik galt: {e}"
                    
                    st.markdown(reply)
                    add_bot_message(reply)
                    
                    # Show flight charts for follow-up recommendations
                    if 'recommended_discs' in st.session_state and st.session_state['recommended_discs']:
                        render_recommendation_flight_charts(
                            st.session_state['recommended_discs'],
                            max_dist,
                            DISC_DATABASE
                        )
                    
                    st.session_state.user_prefs = prefs  # Save updated prefs

# --- SIDEBAR INFO ---
with st.sidebar:
    st.markdown("### Om FindMinDisc")
    st.markdown("Denne bot hjælper dig med at finde den perfekte disc til din spillestil.")
    st.divider()
    if st.button("🔄 Start forfra"):
        reset_conversation()
        st.rerun()
    
    st.divider()
    
    # --- FLIGHT CHART VIEWER ---
    st.markdown("### 📈 Flight Chart")
    
    # Disc search
    disc_search = st.text_input("Søg disc:", placeholder="f.eks. Destroyer")
    
    if disc_search:
        # Find matching discs
        matches = [name for name in DISC_DATABASE.keys() 
                   if disc_search.lower() in name.lower()][:5]
        
        if matches:
            selected_disc = st.selectbox("Vælg disc:", matches)
            
            if selected_disc and selected_disc in DISC_DATABASE:
                disc_data = DISC_DATABASE[selected_disc]
                
                # Calculate recommended distance for this disc
                disc_speed = disc_data.get('speed', 5)
                recommended_dist = disc_speed * 10
                
                # Distance slider for precise calculation
                user_distance = st.slider(
                    "Din kastelængde (m):",
                    min_value=30,
                    max_value=150,
                    value=min(recommended_dist, 90),
                    step=5,
                    help=f"Denne disc anbefales ved ca. {recommended_dist}m kastelængde"
                )
                
                # Show flight chart with precise calculation
                render_flight_chart(
                    selected_disc,
                    disc_data.get('speed', 5),
                    disc_data.get('glide', 4),
                    disc_data.get('turn', 0),
                    disc_data.get('fade', 2),
                    user_distance_m=user_distance
                )
                
                st.caption(f"Producent: {disc_data.get('manufacturer', 'Ukendt')}")
        else:
            st.info("Ingen discs fundet")
    
    st.divider()
    
    # Flight number guide expander
    with st.expander("📖 Hvad betyder flight numbers?"):
        st.markdown(FLIGHT_NUMBER_GUIDE)
    
    # TechDisc-style calculator
    with st.expander("🎯 TechDisc Beregner"):
        st.caption("Baseret på discgolf.digital")
        
        throw_speed = st.slider("Kasthastighed (km/h):", 50, 130, 95, 5)
        nose_angle = st.slider("Nose angle (°):", -5, 5, -3, 1)
        spin_rate = st.slider("Spin (RPM):", 600, 1800, 1200, 100)
        
        # Calculate disc speed from throw speed
        # Formula: disc_speed = 0.185 * throw_mph
        throw_mph = throw_speed / 1.61
        ideal_disc_speed = round(0.185 * throw_mph, 1)
        
        # Calculate stability adjustment
        # Nose angle: -5° = +1.6, +5° = -1.6
        nose_stability = -0.32 * nose_angle
        # Spin: 800=+2.5, 1200=+0.9, 1600=-1.7 → approx -0.005 * (spin - 1200)
        spin_stability = -0.00525 * (spin_rate - 1200)
        total_stability = round(nose_stability + spin_stability, 1)
        
        st.metric("Anbefalet disc speed", f"{ideal_disc_speed}")
        
        if total_stability > 1:
            st.metric("Stabilitets-justering", f"Overstabil (+{total_stability})")
            st.info(f"Ved denne teknik bør du vælge discs med fade {int(total_stability)+1}+ eller turn 0/+1")
        elif total_stability < -1:
            st.metric("Stabilitets-justering", f"Understabil ({total_stability})")
            st.info(f"Ved denne teknik bør du vælge understabile discs med turn -{int(abs(total_stability))} eller lavere")
        else:
            st.metric("Stabilitets-justering", f"Neutral ({total_stability:+.1f})")
            st.info("Din teknik er neutral - vælg discs efter flight numbers")
    
    st.divider()
    st.caption("Drevet af den bedste AI Mikkel har råd til")
    st.caption(f"Database: {len(DISC_DATABASE)} discs")
