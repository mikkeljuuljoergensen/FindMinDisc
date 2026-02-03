"""
Test script for handle_free_form_question function in app.py
Tests the disc golf recommendation AI with specific queries.

This script manually loads only the required functions from app.py
without triggering the Streamlit UI code.
"""

import sys
import os
import json
import re
from unittest.mock import MagicMock

# First, set up the OpenAI API key
api_key = os.environ.get("OPENAI_API_KEY", "")
if not api_key:
    print("ERROR: OPENAI_API_KEY environment variable not set!")
    print("Set it with: $env:OPENAI_API_KEY = 'your-key-here'")
    sys.exit(1)

print("Loading dependencies...")

# Import what we need
from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchRun
from knowledge_base import DiscGolfKnowledgeBase

# Load disc databases
def load_disc_database():
    with open("disc_database.json", "r", encoding="utf-8") as f:
        return json.load(f)

def load_disc_database_full():
    with open("disc_database_full.json", "r", encoding="utf-8") as f:
        return json.load(f)

DISC_DATABASE = load_disc_database()
DISC_DATABASE_FULL = load_disc_database_full()
print(f"Loaded {len(DISC_DATABASE)} discs from database")

# Initialize LLM and search
llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=api_key,
    temperature=0.7
)
search = DuckDuckGoSearchRun()

# Initialize knowledge base
kb = None
kb_enabled = False
try:
    if os.path.exists('./faiss_db/index.faiss'):
        kb = DiscGolfKnowledgeBase(openai_api_key=api_key)
        kb_enabled = True
        print("Knowledge base loaded")
except Exception as e:
    print(f"Knowledge base not available: {e}")


# ========== COPY REQUIRED FUNCTIONS FROM app.py ==========

def fix_flight_numbers_in_response(response, database):
    """
    Post-process AI response to fix any incorrect flight numbers.
    The AI often hallucinates flight numbers from its training data.
    This function forces the correct values from our database.
    """
    lines = response.split('\n')
    current_disc = None
    result_lines = []
    
    for line in lines:
        disc_found = None
        for disc_name in sorted(database.keys(), key=len, reverse=True):
            if re.search(rf'\*\*\s*{re.escape(disc_name)}\s*\*\*|###.*{re.escape(disc_name)}', line, re.IGNORECASE):
                disc_found = disc_name
                break
            elif re.match(rf'^[\*\s]*{re.escape(disc_name)}\s*$', line.strip(), re.IGNORECASE):
                disc_found = disc_name
                break
        
        if disc_found:
            current_disc = disc_found
        
        if current_disc and current_disc in database:
            disc_data = database[current_disc]
            speed = str(disc_data.get('speed', 0))
            glide = str(disc_data.get('glide', 0))
            turn = str(disc_data.get('turn', 0))
            fade = str(disc_data.get('fade', 0))
            
            line = re.sub(
                r'(Flight[:\s]+)\d+/\d+/-?\d+\.?\d*/\d+\.?\d*',
                rf'\g<1>{speed}/{glide}/{turn}/{fade}',
                line, flags=re.IGNORECASE
            )
            line = re.sub(r'(Speed[:\s]+)\d+', rf'\g<1>{speed}', line, flags=re.IGNORECASE)
            line = re.sub(r'(Glide[:\s]+)\d+', rf'\g<1>{glide}', line, flags=re.IGNORECASE)
            line = re.sub(r'(Turn[:\s]+)-?\d+\.?\d*', rf'\g<1>{turn}', line, flags=re.IGNORECASE)
            line = re.sub(r'(Fade[:\s]+)\d+\.?\d*', rf'\g<1>{fade}', line, flags=re.IGNORECASE)
        
        result_lines.append(line)
    
    return '\n'.join(result_lines)


def filter_wrong_speed_discs(response, database, min_speed, max_speed):
    """
    Remove disc recommendations that don't match the requested speed range.
    Returns the filtered response.
    """
    lines = response.split('\n')
    result_lines = []
    skip_until_next_section = False
    current_disc = None
    section_start_idx = -1
    
    for i, line in enumerate(lines):
        disc_found = None
        for disc_name in sorted(database.keys(), key=len, reverse=True):
            if re.search(rf'\*\*\s*{re.escape(disc_name)}\s*\*\*|###.*{re.escape(disc_name)}|\[\s*{re.escape(disc_name)}\s*\]', line, re.IGNORECASE):
                disc_found = disc_name
                break
        
        if disc_found:
            if skip_until_next_section and section_start_idx >= 0:
                result_lines = result_lines[:section_start_idx]
            
            current_disc = disc_found
            disc_data = database.get(current_disc, {})
            current_disc_speed = disc_data.get('speed', 0)
            section_start_idx = len(result_lines)
            
            if current_disc_speed < min_speed or current_disc_speed > max_speed:
                skip_until_next_section = True
                continue
            else:
                skip_until_next_section = False
        
        if skip_until_next_section:
            continue
        
        result_lines.append(line)
    
    while result_lines and result_lines[-1].strip() == '':
        result_lines.pop()
    
    return '\n'.join(result_lines)


def handle_free_form_question(prompt, user_prefs=None):
    """
    Handle any free-form disc golf question using AI + web search.
    Returns AI response with disc recommendations.
    """
    if user_prefs is None:
        user_prefs = {}
    
    prompt_lower = prompt.lower()
    
    # ==== HANDLE "TELL ME MORE" QUESTIONS ====
    tell_more_patterns = ['fortæl', 'forklar', 'mere om', 'hvad med', 'beskriv', 'info om', 'information om']
    is_tell_more = any(p in prompt_lower for p in tell_more_patterns)
    
    discs_in_prompt = []
    for disc_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
        if disc_name.lower() in prompt_lower:
            discs_in_prompt.append(disc_name)
            if len(discs_in_prompt) >= 4:
                break
    
    shown_disc_names = user_prefs.get('shown_discs', [])
    if is_tell_more and not discs_in_prompt and ('dem' in prompt_lower or 'disse' in prompt_lower or 'de ' in prompt_lower):
        discs_in_prompt = shown_disc_names
    
    # If this is a "tell me more" question with specific discs, generate direct response
    if is_tell_more and discs_in_prompt:
        response_parts = ["Selvfølgelig! Her er mere information om de valgte discs:\n"]
        
        for disc_name in discs_in_prompt:
            if disc_name in DISC_DATABASE:
                data = DISC_DATABASE[disc_name]
                speed = data.get('speed', 0)
                glide = data.get('glide', 0)
                turn = data.get('turn', 0)
                fade = data.get('fade', 0)
                manufacturer = data.get('manufacturer', 'Ukendt')
                disc_type = data.get('disc_type', 'Disc')
                
                response_parts.append(f"### **{disc_name}** af {manufacturer}")
                response_parts.append(f"- **Type:** {disc_type}")
                response_parts.append(f"- **Flight:** {speed}/{glide}/{turn}/{fade}")
                
                if turn <= -3:
                    turn_desc = "Meget understabil - drejer meget til højre for højrehåndede"
                elif turn <= -1:
                    turn_desc = "Understabil - mild drejning til højre"
                elif turn == 0:
                    turn_desc = "Neutral - flyver lige"
                else:
                    turn_desc = "Stabil - modstår turn"
                
                if fade >= 3:
                    fade_desc = "Hård fade - kraftig venstredrejning til sidst"
                elif fade >= 2:
                    fade_desc = "Medium fade"
                else:
                    fade_desc = "Blød fade - lander lige"
                
                response_parts.append(f"- **Turn:** {turn_desc}")
                response_parts.append(f"- **Fade:** {fade_desc}")
                
                if speed <= 7 and turn <= -1:
                    skill_rec = "God for begyndere og øvede"
                elif speed >= 11:
                    skill_rec = "Kræver god armhastighed (erfarne spillere)"
                else:
                    skill_rec = "Passer til de fleste spillere"
                
                response_parts.append(f"- **Anbefales til:** {skill_rec}")
                response_parts.append("")
        
        response_parts.append("Vil du se en sammenligning af hvordan de flyver (flight chart)?")
        
        return {
            'response': '\n'.join(response_parts),
            'disc_names': discs_in_prompt,
            'skill_level': user_prefs.get('skill_level', 'intermediate'),
            'max_dist': user_prefs.get('max_dist', 80),
            'disc_type': None
        }
    
    # Try to detect disc type from question
    disc_type = None
    if 'putter' in prompt_lower:
        disc_type = "Putter"
    elif 'approach' in prompt_lower:
        disc_type = "Putter"
    elif 'midrange' in prompt_lower or 'mid-range' in prompt_lower:
        disc_type = "Midrange"
    elif 'fairway' in prompt_lower:
        disc_type = "Fairway driver"
    elif 'distance' in prompt_lower or 'driver' in prompt_lower:
        disc_type = "Distance driver"
    
    # Try to detect explicit speed range
    speed_range_match = re.search(r'(\d+)\s*-\s*(\d+)\s*speed|speed\s*(\d+)\s*-\s*(\d+)', prompt_lower)
    custom_speed_range = None
    if speed_range_match:
        groups = speed_range_match.groups()
        min_speed = int(groups[0] or groups[2])
        max_speed = int(groups[1] or groups[3])
        custom_speed_range = (min_speed, max_speed)
        if not disc_type:
            if max_speed <= 3:
                disc_type = "Putter"
            elif max_speed <= 6:
                disc_type = "Midrange"
            elif max_speed <= 9:
                disc_type = "Fairway driver"
            else:
                disc_type = "Distance driver"
    
    # Try to detect skill level
    skill_level = None
    if 'nybegynder' in prompt_lower or 'begynder' in prompt_lower or 'ny ' in prompt_lower or 'starter' in prompt_lower:
        skill_level = "beginner"
    elif 'øvet' in prompt_lower or 'intermediate' in prompt_lower:
        skill_level = "intermediate"
    elif 'erfaren' in prompt_lower or 'pro' in prompt_lower or 'avanceret' in prompt_lower:
        skill_level = "advanced"
    
    # Try to detect throwing distance
    max_dist = user_prefs.get('max_dist', None)
    numbers = re.findall(r'(\d+)\s*(?:m|meter)', prompt_lower)
    if numbers:
        max_dist = int(numbers[0])
    
    if max_dist is None:
        max_dist = 70 if skill_level == "beginner" else 80
    if skill_level is None:
        skill_level = "intermediate"
    
    # Build search query
    search_terms = prompt.replace('?', '').replace('!', '')
    if skill_level == "beginner":
        search_query = f"best disc golf discs for beginners {search_terms}"
    else:
        search_query = f"disc golf recommendation {search_terms}"
    
    # Knowledge base context
    kb_context = ""
    if kb_enabled and kb:
        try:
            kb_results = kb.get_context_for_query(prompt, max_results=3)
            if kb_results and kb_results != "No relevant information found in knowledge base.":
                kb_context = f"\n\nRELEVANTE REDDIT DISKUSSIONER:\n{kb_results}"
        except Exception as e:
            print(f"Error accessing knowledge base: {e}")
    
    # Web search
    try:
        search_results = search.run(search_query)[:4000]
    except Exception:
        search_results = ""
    
    # Get sample discs from database for context
    sample_discs = []
    shown_disc_names = user_prefs.get('shown_discs', [])
    
    if shown_disc_names:
        sample_discs.append("DISCS BRUGEREN LIGE HAR SET (brug PRÆCIS disse flight numbers):")
        for disc_name in shown_disc_names:
            if disc_name in DISC_DATABASE:
                data = DISC_DATABASE[disc_name]
                speed = data.get('speed', 0)
                glide = data.get('glide', 4)
                turn = data.get('turn', 0)
                fade = data.get('fade', 2)
                sample_discs.append(f"  • {disc_name} ({data.get('manufacturer', '?')}): {speed}/{glide}/{turn}/{fade}")
        sample_discs.append("")
    
    sample_discs.append("ANDRE RELEVANTE DISCS:")
    for name, data in list(DISC_DATABASE.items())[:100]:
        if name in shown_disc_names:
            continue
        speed = data.get('speed', 0)
        
        if skill_level == "beginner" and speed > 9:
            continue
        
        if custom_speed_range:
            min_s, max_s = custom_speed_range
            if not (min_s <= speed <= max_s):
                continue
        elif disc_type:
            speed_ranges = {"Putter": (1, 3), "Midrange": (4, 6), "Fairway driver": (7, 9), "Distance driver": (10, 14)}
            min_s, max_s = speed_ranges.get(disc_type, (1, 14))
            if not (min_s <= speed <= max_s):
                continue
        
        sample_discs.append(f"  • {name} ({data.get('manufacturer', '?')}): {speed}/{data.get('glide', 4)}/{data.get('turn', 0)}/{data.get('fade', 2)}")
        if len(sample_discs) >= 35:
            break
    
    disc_context = "\n".join(sample_discs) if sample_discs else "Ingen relevante discs fundet"
    
    # Build speed requirement text for AI
    speed_requirement = ""
    if custom_speed_range:
        speed_requirement = f"""
🚫🚫🚫 SPEED-KRAV 🚫🚫🚫
Brugeren bad SPECIFIKT om speed {custom_speed_range[0]}-{custom_speed_range[1]}.
Du MÅ ABSOLUT KUN anbefale discs med speed {custom_speed_range[0]}, {(custom_speed_range[0]+custom_speed_range[1])//2}, eller {custom_speed_range[1]}.
Anbefal IKKE Leopard (speed 6), Buzzz (speed 5), eller andre discs UDENFOR dette interval!
Listen ovenfor indeholder KUN godkendte discs med korrekt speed."""
    elif disc_type:
        speed_ranges_text = {"Putter": "1-3", "Midrange": "4-6", "Fairway driver": "7-9", "Distance driver": "10-14"}
        speed_requirement = f"\n⚠️ VIGTIGT: Brugeren bad om {disc_type}s (speed {speed_ranges_text.get(disc_type, '1-14')}). Anbefal KUN discs i dette interval!"
    
    # Build AI prompt
    ai_prompt = f"""Du er en venlig disc golf ekspert der hjælper brugere med at finde de rigtige discs.

Brugerens spørgsmål: "{prompt}"
{speed_requirement}

Brugerens niveau: {"Nybegynder" if skill_level == "beginner" else "Øvet" if skill_level == "intermediate" else "Erfaren"}
Estimeret kastelængde: ca. {max_dist}m

Søgeresultater fra nettet:
{search_results}
{kb_context}

Discs fra vores database (med PRÆCISE flight numbers) - VÆLG KUN FRA DENNE LISTE:
{disc_context}

REGLER:
1. Svar på dansk, venligt og hjælpsomt
2. ⚠️ ABSOLUT KRAV: Vælg KUN discs fra listen ovenfor. Listen er allerede filtreret til at matche brugerens krav!
3. Hvis brugeren spørger om specifikke anbefalinger, giv 2-4 konkrete disc-forslag FRA LISTEN OVENFOR
4. ⚠️ KRITISK: Brug de NØJAGTIGE flight numbers fra databasen ovenfor. Opfind IKKE flight numbers!
5. Brug flight numbers format: Speed/Glide/Turn/Fade
6. Respekter brugerens speed-krav (fx hvis de siger "7-9 speed", må du KUN anbefale discs med speed 7, 8 eller 9)
7. For nybegyndere: anbefal understabile discs (turn -2 eller lavere) og lavere speed
8. Nævn vægt (begyndere: 150-165g, erfarne: 170-175g)
9. Brug Reddit-diskussioner når de er relevante - de viser hvad rigtige spillere faktisk bruger
10. Vær ærlig om hvad der passer til brugerens niveau
11. Hvis du beskriver discs som brugeren allerede har nævnt, brug PRÆCIS de flight numbers fra databasen
12. Hvis du ikke kan finde passende discs på listen, sig det ærligt i stedet for at anbefale forkerte discs

Hvis du anbefaler discs, brug dette format:

### **[DiscNavn]** af [Mærke]
- Flight: X/X/X/X (brug kun tal fra databasen ovenfor!)
- ✅ Hvorfor: ...

Afslut med at spørge om brugeren vil vide mere, sammenligne discs, eller se hvordan de flyver (flight chart)."""

    try:
        response = llm.invoke(ai_prompt).content
        
        # POST-PROCESS: Fix any incorrect flight numbers in the response
        response = fix_flight_numbers_in_response(response, DISC_DATABASE)
        
        # POST-PROCESS: Remove disc recommendations outside the requested speed range
        if custom_speed_range:
            response = filter_wrong_speed_discs(response, DISC_DATABASE, custom_speed_range[0], custom_speed_range[1])
        
        # Extract recommended disc names for potential flight chart
        disc_names = []
        bold_matches = re.findall(r'\*\*([^*]+)\*\*', response)
        
        for bold_text in bold_matches:
            bold_lower = bold_text.lower().strip()
            for db_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
                if db_name.lower() == bold_lower or db_name.lower() in bold_lower:
                    if db_name not in disc_names:
                        disc_names.append(db_name)
                    break
            if len(disc_names) >= 4:
                break
        
        if len(disc_names) < 4:
            for db_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
                if db_name in disc_names:
                    continue
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


# ========== TEST FUNCTIONS ==========

def extract_disc_mentions(response_text, database):
    """Extract all disc names mentioned in the response."""
    mentioned_discs = []
    response_lower = response_text.lower()
    
    for disc_name in sorted(database.keys(), key=len, reverse=True):
        if disc_name.lower() in response_lower:
            pattern = r'\b' + re.escape(disc_name.lower()) + r'\b'
            if re.search(pattern, response_lower):
                mentioned_discs.append(disc_name)
    
    return mentioned_discs


def test_speed_range_query():
    """
    Test 1: "jeg søger en understabil 7-9 speed disc"
    Should ONLY recommend discs with speed 7, 8, or 9
    """
    print("\n" + "="*70)
    print("TEST 1: Speed Range Query (7-9 speed)")
    print("="*70)
    
    prompt = "jeg søger en understabil 7-9 speed disc"
    print(f"Query: {prompt}")
    print("-"*70)
    
    result = handle_free_form_question(prompt)
    response = result['response']
    
    print("\nAI Response (abbreviated):")
    print("-"*40)
    if len(response) > 1500:
        print(response[:1500] + "...[truncated]")
    else:
        print(response)
    print("-"*40)
    
    mentioned_discs = extract_disc_mentions(response, DISC_DATABASE)
    
    wrong_speed_discs = []
    correct_speed_discs = []
    
    for disc_name in mentioned_discs:
        disc_data = DISC_DATABASE.get(disc_name, {})
        speed = disc_data.get('speed', 0)
        if speed < 7 or speed > 9:
            wrong_speed_discs.append(f"{disc_name} (speed {speed})")
        else:
            correct_speed_discs.append(f"{disc_name} (speed {speed})")
    
    print(f"\nDiscs with correct speed (7-9): {correct_speed_discs}")
    print(f"Discs with WRONG speed: {wrong_speed_discs}")
    
    leopard_mentioned = bool(re.search(r'\bleopard\b', response.lower()))
    buzzz_mentioned = bool(re.search(r'\bbuzzz\b', response.lower()))
    
    print(f"\nSpecific checks:")
    print(f"  - Leopard (speed 6) mentioned: {leopard_mentioned}")
    print(f"  - Buzzz (speed 5) mentioned: {buzzz_mentioned}")
    
    passed = len(wrong_speed_discs) == 0 and not leopard_mentioned and not buzzz_mentioned
    
    print(f"\n{'✅ PASS' if passed else '❌ FAIL'}")
    if not passed:
        print("Issues found:")
        if wrong_speed_discs:
            print(f"  - Wrong speed discs mentioned: {wrong_speed_discs}")
        if leopard_mentioned:
            print(f"  - Leopard (speed 6) should not be recommended")
        if buzzz_mentioned:
            print(f"  - Buzzz (speed 5) should not be recommended")
    
    return passed


def test_tell_me_more():
    """
    Test 2: "fortæl mig mere om Photon og Volt"
    Should return database info with correct flight numbers
    """
    print("\n" + "="*70)
    print("TEST 2: Tell Me More Query (Photon and Volt)")
    print("="*70)
    
    prompt = "fortæl mig mere om Photon og Volt"
    print(f"Query: {prompt}")
    print("-"*70)
    
    result = handle_free_form_question(prompt)
    response = result['response']
    
    print("\nAI Response:")
    print("-"*40)
    print(response)
    print("-"*40)
    
    # Expected flight numbers
    # Photon: 11/5/-1/2.5
    # Volt: 8/5/-0.5/2
    
    photon_correct = "11/5/-1/2.5" in response
    volt_correct = "8/5/-0.5/2" in response
    
    if not photon_correct:
        photon_section = ""
        for line in response.split('\n'):
            if 'photon' in line.lower():
                photon_section = line
                break
        photon_correct = "11" in photon_section and "-1" in photon_section and "2.5" in photon_section
    
    if not volt_correct:
        volt_section = ""
        for line in response.split('\n'):
            if 'volt' in line.lower():
                volt_section = line
                break
        volt_correct = "8" in volt_section and "-0.5" in volt_section
    
    print(f"\nFlight number checks:")
    print(f"  - Photon (expected 11/5/-1/2.5): {'✓ Found' if photon_correct else '✗ Not found or incorrect'}")
    print(f"  - Volt (expected 8/5/-0.5/2): {'✓ Found' if volt_correct else '✗ Not found or incorrect'}")
    
    passed = photon_correct and volt_correct
    
    print(f"\n{'✅ PASS' if passed else '❌ FAIL'}")
    if not passed:
        print("Issues found:")
        if not photon_correct:
            print(f"  - Photon flight numbers incorrect (expected 11/5/-1/2.5)")
        if not volt_correct:
            print(f"  - Volt flight numbers incorrect (expected 8/5/-0.5/2)")
    
    return passed


def test_beginner_putter():
    """
    Test 3: "anbefal en god putter til begyndere"
    Should recommend slow speed putters (speed 1-3)
    """
    print("\n" + "="*70)
    print("TEST 3: Beginner Putter Query")
    print("="*70)
    
    prompt = "anbefal en god putter til begyndere"
    print(f"Query: {prompt}")
    print("-"*70)
    
    result = handle_free_form_question(prompt)
    response = result['response']
    
    print("\nAI Response (abbreviated):")
    print("-"*40)
    if len(response) > 1500:
        print(response[:1500] + "...[truncated]")
    else:
        print(response)
    print("-"*40)
    
    mentioned_discs = extract_disc_mentions(response, DISC_DATABASE)
    
    putter_speed_discs = []
    wrong_speed_discs = []
    
    for disc_name in mentioned_discs:
        disc_data = DISC_DATABASE.get(disc_name, {})
        speed = disc_data.get('speed', 0)
        
        if speed <= 3:
            putter_speed_discs.append(f"{disc_name} (speed {speed})")
        else:
            wrong_speed_discs.append(f"{disc_name} (speed {speed})")
    
    print(f"\nDiscs with putter speed (1-3): {putter_speed_discs}")
    print(f"Discs with higher speed: {wrong_speed_discs}")
    
    has_putters = len(putter_speed_discs) > 0
    mostly_correct = len(putter_speed_discs) >= len(wrong_speed_discs)
    
    passed = has_putters and mostly_correct
    
    print(f"\n{'✅ PASS' if passed else '❌ FAIL'}")
    if not passed:
        print("Issues found:")
        if not has_putters:
            print(f"  - No putters (speed 1-3) were recommended")
        if not mostly_correct:
            print(f"  - Too many non-putters recommended: {wrong_speed_discs}")
    
    return passed


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "#"*70)
    print("# FINDMINDISC - handle_free_form_question TEST REPORT")
    print("#"*70)
    
    results = []
    
    try:
        results.append(("Test 1: Speed Range (7-9)", test_speed_range_query()))
    except Exception as e:
        print(f"Test 1 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Test 1: Speed Range (7-9)", False))
    
    try:
        results.append(("Test 2: Tell Me More (Photon/Volt)", test_tell_me_more()))
    except Exception as e:
        print(f"Test 2 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Test 2: Tell Me More (Photon/Volt)", False))
    
    try:
        results.append(("Test 3: Beginner Putter", test_beginner_putter()))
    except Exception as e:
        print(f"Test 3 ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Test 3: Beginner Putter", False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, p in results if p)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print("-"*70)
    print(f"Total: {passed}/{total} tests passed")
    print("="*70)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
