import streamlit as st
import re
import json
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_openai import ChatOpenAI
from retailers import get_product_links, check_disc_tree_stock
from flight_chart import generate_flight_path, get_flight_stats, FLIGHT_NUMBER_GUIDE, calculate_arm_speed_factor

# --- CONFIGURATION ---
st.set_page_config(page_title="FindMinDisc", page_icon="🥏")


def parse_flight_chart_request(prompt):
    """
    Parse natural language requests for flight charts.
    
    Examples:
    - "Vis mig flight charts for Destroyer, Mamba og Zone SS"
    - "Sammenlign Buzzz og Roc3"
    - "Flight chart for Firebird"
    - "Destroyer vs Wraith"
    - "Tilføj Wraith" (adds to existing)
    - "Begynder niveau" / "Pro niveau" (changes level)
    
    Returns dict with 'discs' list and 'arm_speed'
    """
    prompt_lower = prompt.lower()
    
    # Check if this is a flight chart request
    flight_keywords = ['flight chart', 'flightchart', 'sammenlign', 'compare', 'vis mig', 'show me', 'chart for', ' vs ', ' mod ']
    is_chart_request = any(kw in prompt_lower for kw in flight_keywords)
    
    # Check if this is an "add to existing" request
    add_keywords = ['tilføj', 'også', 'add', 'inkluder', 'plus', 'og også', 'hvad med']
    is_add_request = any(kw in prompt_lower for kw in add_keywords)
    
    # Check for arm speed change
    arm_speed = None
    if 'begynder' in prompt_lower or 'slow' in prompt_lower or 'langsom' in prompt_lower:
        arm_speed = 'slow'
    elif 'pro' in prompt_lower or 'fast' in prompt_lower or 'hurtig' in prompt_lower:
        arm_speed = 'fast'
    elif 'øvet' in prompt_lower or 'normal' in prompt_lower or 'mellem' in prompt_lower:
        arm_speed = 'normal'
    
    # Find disc names - try exact match first, then fuzzy match
    disc_names_sorted = sorted(DISC_DATABASE.keys(), key=len, reverse=True)
    
    # Create normalized lookup: "aviar3" -> "Aviar 3", "teebird3" -> "Teebird 3"
    normalized_lookup = {}
    for disc_name in disc_names_sorted:
        # Normalize: lowercase, remove spaces and hyphens
        normalized = disc_name.lower().replace(' ', '').replace('-', '')
        normalized_lookup[normalized] = disc_name
    
    disc_names_found = []
    prompt_remaining = prompt_lower
    prompt_normalized = prompt_lower.replace(' ', '').replace('-', '')
    
    # First try exact matches (with word boundaries)
    for disc_name in disc_names_sorted:
        disc_lower = disc_name.lower()
        pattern = r'(?:^|[^a-zæøå0-9])' + re.escape(disc_lower) + r'(?:[^a-zæøå0-9]|$)'
        if re.search(pattern, prompt_remaining):
            disc_names_found.append(disc_name)
            prompt_remaining = re.sub(pattern, ' ', prompt_remaining, count=1)
            # Also remove from normalized
            prompt_normalized = prompt_normalized.replace(disc_lower.replace(' ', '').replace('-', ''), '', 1)
    
    # Then try normalized matches (handles "Aviar3" -> "Aviar 3")
    for normalized, disc_name in sorted(normalized_lookup.items(), key=lambda x: len(x[0]), reverse=True):
        if disc_name in disc_names_found:
            continue  # Already found
        if normalized in prompt_normalized:
            disc_names_found.append(disc_name)
            prompt_normalized = prompt_normalized.replace(normalized, '', 1)
    
    # Only treat as chart request if:
    # - 2+ discs found (comparison), OR
    # - chart keywords + at least 1 disc, OR
    # - add keywords + at least 1 disc
    # Note: arm_speed alone is NOT enough - we handle that in the chat handler
    if len(disc_names_found) >= 2 or (is_chart_request and disc_names_found) or (is_add_request and disc_names_found):
        return {
            'discs': disc_names_found,
            'arm_speed': arm_speed,
            'is_chart_request': True,
            'is_add_request': is_add_request,
            'is_speed_change': False
        }
    
    # Arm speed change only (no new discs) - let the handler check if there are existing discs
    if arm_speed is not None:
        return {
            'discs': [],
            'arm_speed': arm_speed,
            'is_chart_request': False,  # Not a chart request on its own
            'is_add_request': False,
            'is_speed_change': True
        }
    
    return {'is_chart_request': False}


def handle_free_form_question(prompt, user_prefs=None):
    """
    Handle any free-form disc golf question using AI + web search.
    
    Returns AI response with disc recommendations.
    """
    if user_prefs is None:
        user_prefs = {}
    
    # Extract useful info from the prompt
    prompt_lower = prompt.lower()
    
    # Try to detect disc type from question
    disc_type = None
    if 'putter' in prompt_lower:
        disc_type = "Putter"
    elif 'approach' in prompt_lower:
        disc_type = "Putter"  # Approach discs are typically putters/slow midranges
    elif 'midrange' in prompt_lower or 'mid-range' in prompt_lower:
        disc_type = "Midrange"
    elif 'fairway' in prompt_lower:
        disc_type = "Fairway driver"
    elif 'distance' in prompt_lower or 'driver' in prompt_lower:
        disc_type = "Distance driver"
    
    # Try to detect skill level
    skill_level = "intermediate"
    if 'nybegynder' in prompt_lower or 'begynder' in prompt_lower or 'ny ' in prompt_lower or 'starter' in prompt_lower:
        skill_level = "beginner"
    elif 'øvet' in prompt_lower or 'intermediate' in prompt_lower:
        skill_level = "intermediate"
    elif 'erfaren' in prompt_lower or 'pro' in prompt_lower or 'avanceret' in prompt_lower:
        skill_level = "advanced"
    
    # Try to detect throwing distance
    max_dist = user_prefs.get('max_dist', 70 if skill_level == "beginner" else 90)
    numbers = re.findall(r'(\d+)\s*(?:m|meter)', prompt_lower)
    if numbers:
        max_dist = int(numbers[0])
    
    # Build search query
    search_terms = prompt.replace('?', '').replace('!', '')
    if skill_level == "beginner":
        search_query = f"best disc golf discs for beginners {search_terms}"
    else:
        search_query = f"disc golf recommendation {search_terms}"
    
    # Web search
    try:
        search_results = search.run(search_query)[:4000]
    except Exception:
        search_results = ""
    
    # Get sample discs from database for context
    sample_discs = []
    for name, data in list(DISC_DATABASE.items())[:100]:
        speed = data.get('speed', 0)
        # Filter by skill level
        if skill_level == "beginner" and speed > 9:
            continue
        if disc_type:
            speed_ranges = {"Putter": (1, 3), "Midrange": (4, 6), "Fairway driver": (7, 9), "Distance driver": (10, 14)}
            min_s, max_s = speed_ranges.get(disc_type, (1, 14))
            if not (min_s <= speed <= max_s):
                continue
        sample_discs.append(f"{name} ({data.get('manufacturer', '?')}): {speed}/{data.get('glide', 4)}/{data.get('turn', 0)}/{data.get('fade', 2)}")
        if len(sample_discs) >= 30:
            break
    
    disc_context = "\n".join(sample_discs) if sample_discs else "Ingen relevante discs fundet"
    
    # Build AI prompt
    ai_prompt = f"""Du er en venlig disc golf ekspert der hjælper brugere med at finde de rigtige discs.

Brugerens spørgsmål: "{prompt}"

Brugerens niveau: {"Nybegynder" if skill_level == "beginner" else "Øvet" if skill_level == "intermediate" else "Erfaren"}
Estimeret kastelængde: ca. {max_dist}m

Søgeresultater fra nettet:
{search_results}

Discs fra vores database:
{disc_context}

REGLER:
1. Svar på dansk, venligt og hjælpsomt
2. Hvis brugeren spørger om specifikke anbefalinger, giv 2-4 konkrete disc-forslag
3. Brug flight numbers format: Speed/Glide/Turn/Fade
4. For nybegyndere: anbefal understabile discs (turn -2 eller lavere) og lavere speed
5. Nævn vægt (begyndere: 150-165g, erfarne: 170-175g)
6. Vær ærlig om hvad der passer til brugerens niveau

Hvis du anbefaler discs, brug dette format:

### **[DiscNavn]** af [Mærke]
- Flight: X/X/X/X
- ✅ Hvorfor: ...

Afslut med at spørge om brugeren vil vide mere, sammenligne discs, eller se hvordan de flyver (flight chart)."""

    try:
        response = llm.invoke(ai_prompt).content
        
        # Extract recommended disc names for potential flight chart
        # First try bold text patterns, then fall back to searching full response
        disc_names = []
        response_lower = response.lower()
        
        # Find all bold text patterns first
        bold_matches = re.findall(r'\*\*([^*]+)\*\*', response)
        
        for bold_text in bold_matches:
            bold_lower = bold_text.lower().strip()
            # Check if any disc name matches this bold text
            for db_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
                if db_name.lower() == bold_lower or db_name.lower() in bold_lower:
                    if db_name not in disc_names:
                        disc_names.append(db_name)
                    break
            if len(disc_names) >= 4:
                break
        
        # If we didn't find enough, also search for disc names mentioned without bold
        # But only if they appear at start of line (like "Innova P2" or "P2")
        if len(disc_names) < 4:
            for db_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
                if db_name in disc_names:
                    continue
                # Check for disc name at start of line or after manufacturer name
                pattern = r'(?:^|\n)(?:[A-Za-z]+\s+)?(' + re.escape(db_name) + r')\b'
                if re.search(pattern, response, re.IGNORECASE):
                    disc_names.append(db_name)
                if len(disc_names) >= 4:
                    break
        
        return {
            'response': response,
            'disc_names': disc_names[:4],
            'skill_level': skill_level,
            'max_dist': max_dist,
            'disc_type': disc_type
        }
        
    except Exception as e:
        return {
            'response': f"Beklager, der opstod en fejl: {e}",
            'disc_names': [],
            'skill_level': skill_level,
            'max_dist': max_dist,
            'disc_type': disc_type
        }


def render_flight_chart_comparison(disc_names, arm_speed='normal', throw_hand='right', throw_type='backhand'):
    """
    Render a flight chart comparison using actual flight paths from database.
    
    arm_speed: 'slow' (Begynder), 'normal' (Øvet), 'fast' (Pro)
    throw_hand: 'right' or 'left'
    throw_type: 'backhand' or 'forehand'
    """
    import pandas as pd
    
    # Determine if we need to mirror the chart
    # Mirror for: left-handed backhand OR right-handed forehand
    mirror_chart = (throw_hand == 'left' and throw_type == 'backhand') or \
                   (throw_hand == 'right' and throw_type == 'forehand')
    
    # Map arm speed to Danish labels and path keys
    arm_speed_info = {
        'slow': {'label': 'Begynder', 'path_key': 'flight_path_bh_slow'},
        'normal': {'label': 'Øvet', 'path_key': 'flight_path_bh_normal'},
        'fast': {'label': 'Pro', 'path_key': 'flight_path_bh_fast'}
    }
    
    info = arm_speed_info.get(arm_speed, arm_speed_info['normal'])
    path_key = info['path_key']
    
    # Build throw description
    hand_label = 'Venstrehåndet' if throw_hand == 'left' else 'Højrehåndet'
    throw_label = 'Forhånd' if throw_type == 'forehand' else 'Baghånd'
    
    st.markdown(f"### 🥏 Flight Chart Sammenligning")
    st.markdown(f"*{hand_label} {throw_label} | Niveau: **{info['label']}***")
    
    # Collect disc data from FULL database with flight paths
    discs_with_data = []
    not_found = []
    
    for disc_name in disc_names:
        disc_data = None
        matched_name = None
        for db_name, db_data in DISC_DATABASE_FULL.items():
            if db_name.lower() == disc_name.lower():
                disc_data = db_data
                matched_name = db_name
                break
        
        if disc_data and disc_data.get(path_key):
            discs_with_data.append({
                'name': matched_name,
                'speed': disc_data.get('speed', 5),
                'glide': disc_data.get('glide', 4),
                'turn': disc_data.get('turn', 0),
                'fade': disc_data.get('fade', 2),
                'manufacturer': disc_data.get('manufacturer', 'Ukendt'),
                'path': disc_data.get(path_key, [])
            })
        else:
            not_found.append(disc_name)
    
    if not_found:
        st.warning(f"Kunne ikke finde: {', '.join(not_found)}")
    
    if not discs_with_data:
        st.error("Ingen discs fundet med flight data.")
        return
    
    # Build chart data directly from database paths
    all_data = []
    
    for disc in discs_with_data:
        path = disc['path']
        if not path:
            continue
        
        # Add path points to chart data with point index for ordering
        # Default: Negate x so turn goes LEFT, fade goes RIGHT (RHBH view)
        # If mirrored: Don't negate (for LHBH or RHFH)
        disc_label = f"{disc['name']} ({disc['speed']}/{disc['glide']}/{disc['turn']}/{disc['fade']})"
        for i, p in enumerate(path):
            x_value = p['x'] if mirror_chart else -p['x']
            all_data.append({
                'Disc': disc_label,
                'Turn/Fade': x_value,
                'Distance': round(p['y'] * 0.3048, 1),  # Convert feet to meters
                'point_order': i  # Order for line connection
            })
    
    # Create chart using Altair
    df = pd.DataFrame(all_data)
    
    try:
        import altair as alt
        
        # Calculate axis ranges
        max_dist = df['Distance'].max()
        max_turn_fade = max(abs(df['Turn/Fade'].min()), abs(df['Turn/Fade'].max()), 2)
        
        # Adjust axis title based on mirror state
        if mirror_chart:
            x_title = '← Fade  |  Turn →'
        else:
            x_title = '← Turn  |  Fade →'
        
        chart = alt.Chart(df).mark_line(strokeWidth=3).encode(
            x=alt.X('Turn/Fade:Q', 
                    title=x_title,
                    axis=alt.Axis(labels=False, ticks=False),
                    scale=alt.Scale(domain=[-max_turn_fade - 0.5, max_turn_fade + 0.5])),
            y=alt.Y('Distance:Q', 
                    title='Distance (m)',
                    scale=alt.Scale(domain=[0, max_dist + 5])),
            color=alt.Color('Disc:N', legend=alt.Legend(
                orient='right', 
                title=None,
                labelLimit=200  # Allow longer labels
            )),
            order='point_order:Q',  # Connect points in sequence
            tooltip=['Disc']
        ).properties(
            width=750,
            height=450
        ).configure_axis(
            grid=True
        ).configure_legend(
            labelFontSize=12
        )
        
        # Display full-width chart
        st.altair_chart(chart, use_container_width=True)
        
        # Show stock status for each disc
        st.markdown("#### 🛒 Køb hos Disc Tree")
        for disc in discs_with_data:
            disc_name = disc['name']
            stock_info = check_disc_tree_stock(disc_name)
            
            if stock_info['status'] == 'in_stock':
                price = stock_info.get('price', '')
                price_text = f" ({price} kr)" if price else ""
                st.markdown(f"✅ **{disc_name}**: [På lager{price_text}]({stock_info['url']})")
            elif stock_info['status'] == 'sold_out':
                st.markdown(f"⚠️ **{disc_name}**: [Udsolgt]({stock_info['url']})")
            elif stock_info['status'] == 'not_found':
                search_url = f"https://disctree.dk/search?q={disc_name.replace(' ', '+')}"
                st.markdown(f"❌ **{disc_name}**: [Sælges ikke]({search_url})")
            else:
                # Unknown/error - just show search link
                st.markdown(f"🔍 **{disc_name}**: [Søg]({stock_info.get('url', '')})")
        
    except ImportError:
        pivot_df = df.pivot(index='Distance', columns='Disc', values='Turn/Fade')
        st.line_chart(pivot_df, height=450)
    
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
if "arm_speed" not in st.session_state:
    st.session_state.arm_speed = 'normal'  # Begynder/Øvet/Pro → slow/normal/fast
if "show_chart" not in st.session_state:
    st.session_state.show_chart = False  # Whether to display flight chart
if "throw_hand" not in st.session_state:
    st.session_state.throw_hand = 'right'  # right or left
if "throw_type" not in st.session_state:
    st.session_state.throw_type = 'backhand'  # backhand or forehand

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
    st.session_state.arm_speed = 'normal'  # Default: Øvet
    st.session_state.show_chart = False

# --- START CONVERSATION ---
if st.session_state.step == "start":
    add_bot_message("""Hej! Jeg hjælper dig med at finde den perfekte disc 🥏

**Spørg mig om hvad som helst**, f.eks.:
- *"Jeg er nybegynder og skal bruge 3 discs"*
- *"Hvilken putter er god til putting i vind?"*
- *"Sammenlign Destroyer og Wraith"*

**Eller vælg en disc-type:**
1️⃣ Putter | 2️⃣ Midrange | 3️⃣ Fairway | 4️⃣ Distance""")
    st.session_state.step = "chat"

# --- DISPLAY MESSAGES ---
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# --- DISPLAY PERSISTENT FLIGHT CHART BUTTON ---
if st.session_state.shown_discs and not st.session_state.show_chart:
    if st.button("🥏 Vis mig hvordan de flyver!", type="primary", key="persistent_flight_btn"):
        st.session_state.show_chart = True
        st.rerun()

# --- DISPLAY PERSISTENT FLIGHT CHART ---
if st.session_state.show_chart and st.session_state.shown_discs:
    # Settings selectors in 3 columns
    col1, col2, col3 = st.columns(3)
    with col1:
        niveau_option = st.radio(
            "Niveau:",
            ["Begynder", "Øvet", "Pro"],
            index={"slow": 0, "normal": 1, "fast": 2}.get(st.session_state.arm_speed, 1),
            horizontal=True,
            key="chart_niveau"
        )
        niveau_map = {"Begynder": "slow", "Øvet": "normal", "Pro": "fast"}
        st.session_state.arm_speed = niveau_map[niveau_option]
    with col2:
        hand_option = st.radio(
            "Hånd:",
            ["Højre", "Venstre"],
            index=0 if st.session_state.throw_hand == 'right' else 1,
            horizontal=True,
            key="chart_hand"
        )
        st.session_state.throw_hand = 'right' if hand_option == "Højre" else 'left'
    with col3:
        throw_option = st.radio(
            "Kast:",
            ["Baghånd", "Forhånd"],
            index=0 if st.session_state.throw_type == 'backhand' else 1,
            horizontal=True,
            key="chart_throw"
        )
        st.session_state.throw_type = 'backhand' if throw_option == "Baghånd" else 'forehand'
    
    render_flight_chart_comparison(
        st.session_state.shown_discs, 
        st.session_state.arm_speed,
        st.session_state.throw_hand,
        st.session_state.throw_type
    )

# --- CHAT INPUT ---
if prompt := st.chat_input("Skriv dit svar..."):
    add_user_message(prompt)
    st.chat_message("user").write(prompt)
    
    with st.chat_message("assistant"):
        
        # --- FIRST: Check for natural language flight chart requests ---
        chart_request = parse_flight_chart_request(prompt)
        
        # Handle arm speed change with existing discs (not a full chart request)
        if chart_request.get('is_speed_change') and st.session_state.shown_discs:
            new_arm_speed = chart_request.get('arm_speed')
            if new_arm_speed:
                st.session_state.arm_speed = new_arm_speed
            niveau_labels = {'slow': 'Begynder', 'normal': 'Øvet', 'fast': 'Pro'}
            niveau_label = niveau_labels.get(st.session_state.arm_speed, 'Øvet')
            reply = f"Skiftet til **{niveau_label}** niveau:"
            st.markdown(reply)
            add_bot_message(reply)
            st.session_state.show_chart = True
            st.rerun()
        
        elif chart_request.get('is_chart_request'):
            new_discs = chart_request.get('discs', [])
            is_add = chart_request.get('is_add_request', False)
            new_arm_speed = chart_request.get('arm_speed')
            
            # Update arm speed if specified
            if new_arm_speed:
                st.session_state.arm_speed = new_arm_speed
            
            arm_speed = st.session_state.arm_speed
            niveau_labels = {'slow': 'Begynder', 'normal': 'Øvet', 'fast': 'Pro'}
            niveau_label = niveau_labels.get(arm_speed, 'Øvet')
            
            # Handle adding discs
            if is_add and st.session_state.shown_discs and new_discs:
                all_discs = list(st.session_state.shown_discs)
                for disc in new_discs:
                    if disc not in all_discs:
                        all_discs.append(disc)
                reply = f"Tilføjet **{', '.join(new_discs)}** ({niveau_label} niveau):"
            # Handle new chart request
            elif new_discs:
                all_discs = new_discs
                reply = f"Flight charts for **{', '.join(all_discs)}** ({niveau_label} niveau):"
            else:
                # No discs and no previous discs
                reply = "Nævn mindst én disc - f.eks. 'Sammenlign Destroyer og Mamba'"
                st.markdown(reply)
                add_bot_message(reply)
                st.rerun()
            
            st.markdown(reply)
            add_bot_message(reply)
            
            # Update session state - chart will render after rerun
            st.session_state.step = "done"
            st.session_state.shown_discs = all_discs
            st.session_state.show_chart = True
            
            follow_up = "*Tilføj flere: 'Også Wraith'* | *Skift niveau: 'Pro' eller 'Begynder'*"
            add_bot_message(follow_up)
            st.rerun()
        
        # --- STEP: CHAT (handles both structured and free-form) ---
        elif st.session_state.step == "chat":
            prompt_lower = prompt.lower()
            
            # Check for structured disc type selection (1, 2, 3, 4)
            if prompt.strip() in ["1", "2", "3", "4"]:
                disc_types = {"1": "Putter", "2": "Midrange", "3": "Fairway driver", "4": "Distance driver"}
                st.session_state.user_prefs["disc_type"] = disc_types[prompt.strip()]
                reply = f"Fedt, du leder efter en **{st.session_state.user_prefs['disc_type']}**!\n\nHvor langt kaster du cirka? (i meter)"
                st.write(reply)
                add_bot_message(reply)
                st.session_state.step = "ask_distance"
            elif "putter" in prompt_lower and len(prompt) < 15:
                st.session_state.user_prefs["disc_type"] = "Putter"
                reply = "Fedt, du leder efter en **Putter**!\n\nHvor langt kaster du cirka? (i meter)"
                st.write(reply)
                add_bot_message(reply)
                st.session_state.step = "ask_distance"
            elif ("midrange" in prompt_lower or "mid-range" in prompt_lower) and len(prompt) < 20:
                st.session_state.user_prefs["disc_type"] = "Midrange"
                reply = "Fedt, du leder efter en **Midrange**!\n\nHvor langt kaster du cirka? (i meter)"
                st.write(reply)
                add_bot_message(reply)
                st.session_state.step = "ask_distance"
            elif "fairway" in prompt_lower and len(prompt) < 20:
                st.session_state.user_prefs["disc_type"] = "Fairway driver"
                reply = "Fedt, du leder efter en **Fairway driver**!\n\nHvor langt kaster du cirka? (i meter)"
                st.write(reply)
                add_bot_message(reply)
                st.session_state.step = "ask_distance"
            elif "distance" in prompt_lower and "driver" in prompt_lower and len(prompt) < 25:
                st.session_state.user_prefs["disc_type"] = "Distance driver"
                reply = "Fedt, du leder efter en **Distance driver**!\n\nHvor langt kaster du cirka? (i meter)"
                st.write(reply)
                add_bot_message(reply)
                st.session_state.step = "ask_distance"
            else:
                # Free-form question - use AI to answer
                with st.spinner("Søger efter svar..."):
                    result = handle_free_form_question(prompt, st.session_state.user_prefs)
                    
                    response = result['response']
                    disc_names = result.get('disc_names', [])
                    
                    # Add buy links for recommended discs
                    for disc in disc_names:
                        if disc and len(disc) >= 2:
                            links = get_product_links(disc)
                            buy_link_parts = []
                            if 'Disc Tree' in links:
                                buy_link_parts.append(f"[Disc Tree]({links['Disc Tree']})")
                            if 'NewDisc' in links:
                                buy_link_parts.append(f"[NewDisc]({links['NewDisc']})")
                            
                            if buy_link_parts:
                                buy_links = f"\n🛒 **Køb {disc}:** {' | '.join(buy_link_parts)}"
                                # Try to add after "✅ Hvorfor:" line for this disc
                                # Match disc name (with or without **) followed by content up to Hvorfor line
                                pattern = rf'(\*?\*?{re.escape(disc)}\*?\*?.*?✅ Hvorfor:[^\n]*)'
                                match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
                                if match:
                                    response = response.replace(match.group(1), match.group(1) + buy_links)
                                else:
                                    # Fallback: add at the end if pattern not found
                                    response += f"\n{buy_links}"
                    
                    st.markdown(response)
                    add_bot_message(response)
                    
                    # Store recommendations for later flight chart (only shown when user asks)
                    if disc_names:
                        st.session_state['recommended_discs'] = disc_names
                        st.session_state.user_prefs['max_dist'] = result.get('max_dist', 80)
                        st.session_state.user_prefs['skill_level'] = result.get('skill_level', 'intermediate')
                        
                        # Prepare chart settings but don't show yet
                        skill = result.get('skill_level', 'intermediate')
                        st.session_state.arm_speed = 'slow' if skill == 'beginner' else 'normal'
                        st.session_state.shown_discs = disc_names
                        # Button is shown persistently outside this block
                    
                    st.session_state.step = "done"
        
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
                        if disc and len(disc) >= 2:
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
                
                # Store chart settings but don't show automatically - wait for user to ask
                if 'recommended_discs' in st.session_state and st.session_state['recommended_discs']:
                    arm_speed = 'slow' if max_dist < 70 else 'normal'
                    st.session_state.arm_speed = arm_speed
                    st.session_state.shown_discs = st.session_state['recommended_discs']
                    # Button is shown persistently outside this block
                
                st.session_state.step = "done"
        
        # --- STEP: DONE - CONTINUE CONVERSATION ---
        elif st.session_state.step == "done":
            if "forfra" in prompt.lower():
                reset_conversation()
                st.rerun()
            else:
                prompt_lower = prompt.lower()
                
                # Check if user wants to see flight chart
                wants_flight_chart = any(kw in prompt_lower for kw in [
                    'flight', 'flyver', 'flyvning', 'chart', 'graf', 'kurve', 'bane', 'vis'
                ]) and st.session_state.get('shown_discs')
                
                if wants_flight_chart:
                    # Show the flight chart
                    reply = "Her er flight charts for de anbefalede discs:"
                    st.markdown(reply)
                    add_bot_message(reply)
                    st.session_state.show_chart = True
                    
                    # Add follow-up question about plastic
                    disc_names = st.session_state.get('shown_discs', [])
                    if disc_names:
                        disc_list = ', '.join(disc_names)
                        followup = f"\n\n💡 *Vil du vide hvilken plastik der passer bedst til {disc_list}? Eller spørg mig om noget andet!*"
                        st.markdown(followup)
                        add_bot_message(followup)
                    
                    st.rerun()
                
                # Check if this is a plastic question (don't need new recommendations)
                is_plastic_question = 'plastik' in prompt_lower or 'plastic' in prompt_lower
                
                # Check if user wants new recommendations
                wants_new_recs = any(kw in prompt_lower for kw in [
                    'anbefal', 'foreslå', 'alternativ', 'andre discs', 'ny disc', 'nye discs',
                    'jeg vil have', 'jeg skal bruge', 'find mig'
                ])
                
                # Check if user is asking about a specific disc type
                asking_disc_type = any(kw in prompt_lower for kw in [
                    'putter', 'midrange', 'mid-range', 'fairway', 'distance', 'driver', 'approach'
                ])
                
                # Simple questions about plastic - answer directly without new search
                if is_plastic_question and not wants_new_recs:
                    with st.spinner("Finder plastik-info..."):
                        # Get previously recommended discs
                        prev_discs = st.session_state.get('recommended_discs', [])
                        disc_context = ""
                        if prev_discs:
                            disc_context = f"De discs vi talte om: {', '.join(prev_discs)}"
                        
                        plastic_prompt = f"""Brugerens spørgsmål: "{prompt}"

{disc_context}

PLASTIK GUIDE:
{PLASTIC_GUIDE}

Svar på dansk. Giv konkrete plastik-anbefalinger baseret på de discs brugeren har fået anbefalet.
Hvis de spurgte om specifikke discs, anbefal plastik til dem.
Vær kort og præcis - brugeren har allerede fået disc-anbefalinger."""

                        try:
                            reply = llm.invoke(plastic_prompt).content
                        except Exception as e:
                            reply = f"Beklager, noget gik galt: {e}"
                        
                        st.markdown(reply)
                        add_bot_message(reply)
                
                # General questions - answer without giving new recommendations
                elif not wants_new_recs and not asking_disc_type:
                    with st.spinner("Tænker..."):
                        # Get conversation context
                        conversation_context = "\n".join([f"{m['role']}: {m['content'][:200]}" for m in st.session_state.messages[-6:]])
                        prev_discs = st.session_state.get('recommended_discs', [])
                        
                        # Search for relevant info
                        try:
                            search_results = search.run(f"disc golf {prompt}")[:2000]
                        except:
                            search_results = ""
                        
                        general_prompt = f"""Du er en venlig disc golf ekspert.

Tidligere samtale:
{conversation_context}

Discs vi har talt om: {', '.join(prev_discs) if prev_discs else 'Ingen endnu'}

Brugerens spørgsmål: "{prompt}"

Søgeresultater:
{search_results}

REGLER:
- Svar på dansk, venligt og informativt
- DETTE ER ET GENERELT SPØRGSMÅL - giv IKKE nye disc-anbefalinger medmindre brugeren specifikt beder om det
- Svar på spørgsmålet direkte baseret på din viden og søgeresultaterne
- Hvis spørgsmålet handler om de discs vi talte om, referer til dem
- Hold svaret kort og relevant"""

                        try:
                            reply = llm.invoke(general_prompt).content
                        except Exception as e:
                            reply = f"Beklager, noget gik galt: {e}"
                        
                        st.markdown(reply)
                        add_bot_message(reply)
                
                else:
                    # User wants new recommendations
                    with st.spinner("Søger..."):
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
                        if "putter" in prompt_lower:
                            prefs["disc_type"] = "Putter"
                        elif "approach" in prompt_lower:
                            prefs["disc_type"] = "Putter"  # Approach discs are typically putters
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
- VIGTIGST: Vurder først om brugeren beder om nye disc-anbefalinger eller bare stiller et generelt spørgsmål
- For GENERELLE spørgsmål (fx "hvilken disc er bedst?", "hvem vandt VM?", "hvordan kaster man?"): Svar informativt UDEN at give nye disc-anbefalinger. Brug din viden og søgeresultaterne.
- For ANBEFALINGS-spørgsmål (fx "anbefal en putter", "jeg vil have en ny disc"): Giv 2-4 konkrete disc-forslag fra databasen
- Hvis brugeren ændrer distance eller disc-type, giv NYE anbefalinger
- Svar altid på dansk
- PRIORITER discs fra databasen da de har verificerede flight numbers
- For kastere under 70m: anbefal letvægt (150-165g) og understabile discs
- Hvis disc-typen ikke passer til distancen, SIG DET og foreslå en bedre type
- Hvis brugeren spørger om plastik, brug PLASTIK VIDEN ovenfor

Søgeresultater fra nettet:
{search_results}

Hvis du giver nye anbefalinger (KUN hvis brugeren beder om det), brug dette format:

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
                                if disc and len(disc) >= 2:
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
                        
                        # Store chart settings but don't show automatically
                        if 'recommended_discs' in st.session_state and st.session_state['recommended_discs']:
                            arm_speed = 'slow' if max_dist < 70 else 'normal'
                            st.session_state.arm_speed = arm_speed
                            st.session_state.shown_discs = st.session_state['recommended_discs']
                            # Button is shown persistently outside this block
                        
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
    
    # Flight number guide expander
    with st.expander("📖 Hvad betyder flight numbers?"):
        st.markdown(FLIGHT_NUMBER_GUIDE)
    
    st.divider()
    st.caption("Drevet af den bedste AI Mikkel har råd til")
