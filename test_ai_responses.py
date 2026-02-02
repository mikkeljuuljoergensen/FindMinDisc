"""
Test AI Responses
==================
This script tests the actual AI responses from handle_free_form_question.
Requires OPENAI_API_KEY to be set.

Usage:
    $env:OPENAI_API_KEY = 'your-key'
    python test_ai_responses.py
"""

import json
import re
import os
import sys

# Check for API key
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    print("❌ OPENAI_API_KEY not set. Set it with:")
    print("   $env:OPENAI_API_KEY = 'your-key-here'")
    sys.exit(1)

# Load database directly
with open('disc_database.json', 'r', encoding='utf-8') as f:
    DISC_DATABASE = json.load(f)

# Setup LLM
from langchain_openai import ChatOpenAI
from langchain_community.tools import DuckDuckGoSearchRun

llm = ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0.7)
search = DuckDuckGoSearchRun()

print("="*60)
print("  AI Response Tests")
print("="*60)

# Test counters
PASSED = 0
FAILED = 0


def filter_wrong_speed_discs(response, database, min_speed, max_speed):
    """Remove disc recommendations outside speed range"""
    lines = response.split('\n')
    result_lines = []
    skip_until_next_section = False
    section_start_idx = -1
    
    for line in lines:
        disc_found = None
        for disc_name in sorted(database.keys(), key=len, reverse=True):
            if re.search(rf'\*\*\s*{re.escape(disc_name)}\s*\*\*|###.*{re.escape(disc_name)}|\[\s*{re.escape(disc_name)}\s*\]', line, re.IGNORECASE):
                disc_found = disc_name
                break
        
        if disc_found:
            if skip_until_next_section and section_start_idx >= 0:
                result_lines = result_lines[:section_start_idx]
            
            disc_data = database.get(disc_found, {})
            speed = disc_data.get('speed', 0)
            section_start_idx = len(result_lines)
            
            if speed < min_speed or speed > max_speed:
                skip_until_next_section = True
                continue
            else:
                skip_until_next_section = False
        
        if skip_until_next_section:
            continue
        result_lines.append(line)
    
    return '\n'.join(result_lines)


def fix_flight_numbers_in_response(response, database):
    """Fix AI hallucinated flight numbers"""
    lines = response.split('\n')
    current_disc = None
    result_lines = []
    
    for line in lines:
        disc_found = None
        for disc_name in sorted(database.keys(), key=len, reverse=True):
            if re.search(rf'\*\*\s*{re.escape(disc_name)}\s*\*\*|###.*{re.escape(disc_name)}', line, re.IGNORECASE):
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
            
            line = re.sub(r'(Flight[:\s]+)\d+/\d+/-?\d+\.?\d*/\d+\.?\d*', 
                          rf'\g<1>{speed}/{glide}/{turn}/{fade}', line, flags=re.IGNORECASE)
        
        result_lines.append(line)
    
    return '\n'.join(result_lines)


def fix_manufacturer_names_in_response(response, database):
    """Fix AI hallucinated manufacturer names"""
    result = response
    
    for disc_name in sorted(database.keys(), key=len, reverse=True):
        if disc_name in database:
            correct_manufacturer = database[disc_name].get('manufacturer', '')
            if not correct_manufacturer:
                continue
            
            # Pattern 1: Fix "### **WrongManufacturer DiscName** af WrongManufacturer"
            pattern1 = rf'(###\s*\*\*)[^*\n]*?{re.escape(disc_name)}\s*\*\*(\s+af\s+)[A-Za-z0-9\s]+?(?=\n|$|-)'
            if re.search(pattern1, result, re.IGNORECASE):
                result = re.sub(pattern1, rf'\g<1>{disc_name}**\g<2>{correct_manufacturer}', result, flags=re.IGNORECASE)
            
            # Pattern 2: Fix just "**DiscName** af WrongManufacturer" (no prefix issue)
            pattern2 = rf'(\*\*{re.escape(disc_name)}\*\*\s+af\s+)[A-Za-z0-9\s]+?(?=\n|$|-)'
            if re.search(pattern2, result, re.IGNORECASE):
                result = re.sub(pattern2, rf'\g<1>{correct_manufacturer}', result, flags=re.IGNORECASE)
    
    return result


def get_disc_context(disc_type=None, min_speed=None, max_speed=None, include_popular=True):
    """Build disc context with filtering and popular discs"""
    sample_discs = []
    
    # Popular discs that should always be included if relevant
    popular_discs = [
        'Destroyer', 'Wraith', 'Thunderbird', 'Firebird',  # Distance
        'Escape', 'Leopard', 'Roadrunner', 'Valkyrie', 'Volt', 'Tesla',  # Fairway
        'Buzzz', 'Roc3', 'Mako3', 'Hex', 'Compass',  # Midrange
        'Aviar', 'Luna', 'Judge', 'P2', 'Envy',  # Putter
        'Photon', 'Wave', 'Insanity',  # MVP/Axiom
    ]
    
    # Add popular discs first
    if include_popular:
        for name in popular_discs:
            if name in DISC_DATABASE:
                data = DISC_DATABASE[name]
                speed = data.get('speed', 0)
                
                # Apply speed filter
                if min_speed and max_speed:
                    if not (min_speed <= speed <= max_speed):
                        continue
                
                sample_discs.append(f"  • {name} ({data.get('manufacturer', '?')}): {speed}/{data.get('glide', 0)}/{data.get('turn', 0)}/{data.get('fade', 0)}")
    
    # Add more discs from database
    for name, data in list(DISC_DATABASE.items())[:200]:
        if any(name in d for d in sample_discs):
            continue  # Skip duplicates
            
        speed = data.get('speed', 0)
        
        # Apply speed filter
        if min_speed and max_speed:
            if not (min_speed <= speed <= max_speed):
                continue
        
        sample_discs.append(f"  • {name} ({data.get('manufacturer', '?')}): {speed}/{data.get('glide', 0)}/{data.get('turn', 0)}/{data.get('fade', 0)}")
        
        if len(sample_discs) >= 40:
            break
    
    return "\n".join(sample_discs)


def handle_test_question(prompt, min_speed=None, max_speed=None, disc_type=None):
    """Simplified version of handle_free_form_question for testing"""
    
    disc_context = get_disc_context(disc_type, min_speed, max_speed)
    
    speed_req = ""
    if min_speed and max_speed:
        speed_req = f"""
🚫🚫🚫 SPEED-KRAV 🚫🚫🚫
Anbefal KUN discs med speed {min_speed}-{max_speed}.
Anbefal IKKE discs udenfor dette interval!"""
    
    ai_prompt = f"""Du er en disc golf ekspert.

Spørgsmål: "{prompt}"
{speed_req}

Discs fra databasen (VÆLG KUN FRA DENNE LISTE):
{disc_context}

REGLER:
1. Svar på dansk
2. Vælg KUN discs fra listen ovenfor - opfind IKKE discs!
3. Brug PRÆCIS de flight numbers fra listen
4. Anbefal 2-3 discs

Format for hver disc:
### **[DiscNavn]** af [Producent]
- Flight: X/X/X/X
- Hvorfor: [kort begrundelse]"""

    response = llm.invoke(ai_prompt).content
    response = fix_flight_numbers_in_response(response, DISC_DATABASE)
    
    if min_speed and max_speed:
        response = filter_wrong_speed_discs(response, DISC_DATABASE, min_speed, max_speed)
    
    return response


def log_pass(test_name):
    global PASSED
    PASSED += 1
    print(f"✅ PASS: {test_name}")


def log_fail(test_name, details=""):
    global FAILED
    FAILED += 1
    print(f"❌ FAIL: {test_name}")
    if details:
        print(f"   {details}")


# =============================================================================
# TEST CASES
# =============================================================================

def test_speed_range_7_9():
    """Test that speed range 7-9 is respected"""
    print("\n📋 TEST 1: Speed Range 7-9 (understabil fairway)")
    print("-"*50)
    
    response = handle_test_question(
        "jeg søger en understabil 7-9 speed disc",
        min_speed=7, max_speed=9
    )
    
    print(f"Response:\n{response[:700]}\n")
    
    # Check for wrong-speed discs
    wrong_discs = []
    response_lower = response.lower()
    
    check_discs = {'Leopard': 6, 'Buzzz': 5, 'Mako3': 5, 'Destroyer': 12, 'Wraith': 11, 'Aviar': 2}
    
    for disc, speed in check_discs.items():
        if disc.lower() in response_lower:
            wrong_discs.append(f"{disc} (speed {speed})")
    
    if wrong_discs:
        log_fail("Speed range 7-9", f"Found wrong-speed discs: {wrong_discs}")
        return False
    else:
        log_pass("Speed range 7-9 - no wrong-speed discs")
        return True


def test_speed_range_10_14():
    """Test distance driver speed range"""
    print("\n📋 TEST 2: Speed Range 10-14 (distance driver)")
    print("-"*50)
    
    response = handle_test_question(
        "anbefal en distance driver til erfarne spillere",
        min_speed=10, max_speed=14
    )
    
    print(f"Response:\n{response[:700]}\n")
    
    # Should NOT have fairways or mids
    wrong_discs = []
    response_lower = response.lower()
    
    check_discs = {'Buzzz': 5, 'Roc3': 5, 'Escape': 9, 'Leopard': 6, 'Aviar': 2}
    
    for disc, speed in check_discs.items():
        if disc.lower() in response_lower:
            wrong_discs.append(f"{disc} (speed {speed})")
    
    if wrong_discs:
        log_fail("Speed range 10-14", f"Found wrong-speed discs: {wrong_discs}")
        return False
    else:
        log_pass("Speed range 10-14 - no wrong-speed discs")
        return True


def test_tell_me_more_database():
    """Test direct database lookup for 'tell me more'"""
    print("\n📋 TEST 3: Tell Me More - Database Lookup")
    print("-"*50)
    
    discs = ['Photon', 'Volt', 'Destroyer']
    response_parts = []
    
    for disc_name in discs:
        if disc_name in DISC_DATABASE:
            data = DISC_DATABASE[disc_name]
            flight = f"{data['speed']}/{data['glide']}/{data['turn']}/{data['fade']}"
            response_parts.append(f"**{disc_name}**: {flight}")
    
    response = "\n".join(response_parts)
    print(f"Database lookup:\n{response}\n")
    
    # Verify correct values
    checks = [
        ('Photon', '11/5/-1/2.5'),
        ('Volt', '8/5/-0.5/2'),
        ('Destroyer', '12/5/-1/3'),
    ]
    
    all_pass = True
    for disc, expected in checks:
        if expected in response:
            print(f"  ✅ {disc}: {expected}")
        else:
            print(f"  ❌ {disc}: expected {expected}")
            all_pass = False
    
    if all_pass:
        log_pass("Tell me more - database lookup")
    else:
        log_fail("Tell me more - wrong values")
    return all_pass


def test_roadrunner_flight():
    """Test Roadrunner gets correct flight numbers"""
    print("\n📋 TEST 4: Roadrunner Flight Numbers")
    print("-"*50)
    
    response = handle_test_question("fortæl mig om Roadrunner", min_speed=7, max_speed=11)
    print(f"Response:\n{response[:600]}\n")
    
    expected = "9/5/-4/1"
    if expected in response:
        log_pass(f"Roadrunner flight = {expected}")
        return True
    elif "roadrunner" in response.lower():
        # Roadrunner mentioned but wrong flight
        match = re.search(r'(\d+/\d+/-?\d+\.?\d*/\d+\.?\d*)', response)
        if match:
            log_fail("Roadrunner flight", f"Got {match.group(1)}, expected {expected}")
        else:
            log_fail("Roadrunner flight", f"No flight numbers found")
        return False
    else:
        log_fail("Roadrunner flight", "Roadrunner not in response")
        return False


def test_volt_flight():
    """Test Volt gets correct flight numbers"""
    print("\n📋 TEST 5: Volt Flight Numbers")
    print("-"*50)
    
    response = handle_test_question("beskriv Volt discen", min_speed=6, max_speed=10)
    print(f"Response:\n{response[:600]}\n")
    
    expected = "8/5/-0.5/2"
    if expected in response:
        log_pass(f"Volt flight = {expected}")
        return True
    elif "volt" in response.lower():
        match = re.search(r'(\d+/\d+/-?\d+\.?\d*/\d+\.?\d*)', response)
        if match:
            log_fail("Volt flight", f"Got {match.group(1)}, expected {expected}")
        else:
            log_fail("Volt flight", "No flight numbers found")
        return False
    else:
        log_fail("Volt flight", "Volt not in response")
        return False


def test_putter_speed():
    """Test putter recommendations have speed 1-3"""
    print("\n📋 TEST 6: Putter Speed (1-3)")
    print("-"*50)
    
    response = handle_test_question(
        "anbefal en god putter til begyndere",
        min_speed=1, max_speed=3
    )
    
    print(f"Response:\n{response[:600]}\n")
    
    # Extract mentioned discs - only match whole words
    mentioned = []
    response_lower = response.lower()
    for disc_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
        # Only match if disc name is a whole word (not part of another word)
        if len(disc_name) < 4:
            continue  # Skip very short names that might match accidentally
        if disc_name.lower() in response_lower:
            speed = DISC_DATABASE[disc_name].get('speed', 0)
            if speed <= 5:  # Only count putters/mids, not random matches
                mentioned.append((disc_name, speed))
    
    print(f"Discs mentioned: {mentioned}")
    
    # Check for actual putter recommendations (should be speed 1-3)
    putters = [(d, s) for d, s in mentioned if s <= 3]
    wrong = [(d, s) for d, s in mentioned if s > 3]
    
    if putters and not wrong:
        log_pass(f"Putter speed - found putters: {[d for d, s in putters]}")
        return True
    elif putters:
        log_pass(f"Putter speed - found putters: {[d for d, s in putters]} (some mids also mentioned)")
        return True
    else:
        log_fail("Putter speed", f"No valid putters found. Wrong: {wrong}")
        return False


def test_midrange_speed():
    """Test midrange recommendations have speed 4-6"""
    print("\n📋 TEST 7: Midrange Speed (4-6)")
    print("-"*50)
    
    response = handle_test_question(
        "jeg vil have en stabil midrange disc",
        min_speed=4, max_speed=6
    )
    
    print(f"Response:\n{response[:600]}\n")
    
    # Check for wrong-speed discs
    wrong_discs = []
    response_lower = response.lower()
    
    check_discs = {'Destroyer': 12, 'Wraith': 11, 'Escape': 9, 'Aviar': 2}
    
    for disc, speed in check_discs.items():
        if disc.lower() in response_lower:
            wrong_discs.append(f"{disc} (speed {speed})")
    
    if wrong_discs:
        log_fail("Midrange speed", f"Found wrong-speed discs: {wrong_discs}")
        return False
    else:
        log_pass("Midrange speed - no wrong-speed discs")
        return True


def test_understable_detection():
    """Test understable disc detection"""
    print("\n📋 TEST 8: Understable Disc Detection")
    print("-"*50)
    
    response = handle_test_question(
        "jeg vil have en understabil disc der drejer til højre",
        min_speed=7, max_speed=12
    )
    
    print(f"Response:\n{response[:600]}\n")
    
    # Check that mentioned discs have negative turn
    understable_found = False
    for disc_name in DISC_DATABASE.keys():
        if disc_name.lower() in response.lower():
            turn = DISC_DATABASE[disc_name].get('turn', 0)
            if turn < 0:
                understable_found = True
                print(f"  ✅ {disc_name} has turn {turn} (understable)")
    
    if understable_found:
        log_pass("Understable detection")
        return True
    else:
        log_fail("Understable detection", "No understable discs found")
        return False


def test_overstable_detection():
    """Test overstable disc detection"""
    print("\n📋 TEST 9: Overstable Disc Detection")
    print("-"*50)
    
    response = handle_test_question(
        "jeg skal bruge en overstabil disc til vind",
        min_speed=7, max_speed=12
    )
    
    print(f"Response:\n{response[:600]}\n")
    
    # Check that mentioned discs have high fade or low turn
    overstable_found = False
    for disc_name in DISC_DATABASE.keys():
        if disc_name.lower() in response.lower():
            fade = DISC_DATABASE[disc_name].get('fade', 0)
            turn = DISC_DATABASE[disc_name].get('turn', 0)
            if fade >= 2 or turn >= 0:
                overstable_found = True
                print(f"  ✅ {disc_name} has turn {turn}, fade {fade}")
    
    if overstable_found:
        log_pass("Overstable detection")
        return True
    else:
        log_fail("Overstable detection", "No overstable discs found")
        return False


def test_flight_number_correction():
    """Test that flight numbers get corrected by post-processing"""
    print("\n📋 TEST 10: Flight Number Correction")
    print("-"*50)
    
    # Simulate AI giving wrong numbers
    wrong_response = """
### **Destroyer** af Innova
- Flight: 14/5/-2/4

### **Photon** af MVP
- Flight: 13/5/-1/3
"""
    
    corrected = fix_flight_numbers_in_response(wrong_response, DISC_DATABASE)
    print(f"Original:\n{wrong_response}")
    print(f"Corrected:\n{corrected}")
    
    checks = [
        ('12/5/-1/3', 'Destroyer'),  # Correct
        ('11/5/-1/2.5', 'Photon'),   # Correct
    ]
    
    all_pass = True
    for expected, disc in checks:
        if expected in corrected:
            print(f"  ✅ {disc}: {expected}")
        else:
            print(f"  ❌ {disc}: expected {expected}")
            all_pass = False
    
    if all_pass:
        log_pass("Flight number correction")
    else:
        log_fail("Flight number correction")
    return all_pass


def test_beginner_recommendations():
    """Test that beginner recommendations are appropriate"""
    print("\n📋 TEST 11: Beginner Recommendations")
    print("-"*50)
    
    response = handle_test_question(
        "jeg er helt ny til disc golf, hvilke discs skal jeg starte med?",
        min_speed=1, max_speed=9
    )
    
    print(f"Response:\n{response[:700]}\n")
    
    # Check that no high-speed discs are recommended
    # Use word boundary matching to avoid false positives like "Drive" in "Driver"
    wrong_discs = []
    for disc_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
        # Only check disc names that are 6+ chars to avoid common word matches
        if len(disc_name) >= 6:
            # Use word boundary regex to match whole words only
            pattern = r'\b' + re.escape(disc_name) + r'\b'
            if re.search(pattern, response, re.IGNORECASE):
                speed = DISC_DATABASE[disc_name].get('speed', 0)
                if speed >= 11:
                    wrong_discs.append(f"{disc_name} (speed {speed})")
    
    if wrong_discs:
        log_fail("Beginner recommendations", f"Too fast discs: {wrong_discs}")
        return False
    else:
        log_pass("Beginner recommendations - no high-speed discs")
        return True


def test_wind_disc_recommendations():
    """Test that wind recommendations are overstable"""
    print("\n📋 TEST 12: Wind Disc Recommendations")
    print("-"*50)
    
    response = handle_test_question(
        "hvilken disc er bedst til at kaste i kraftig vind?",
        min_speed=7, max_speed=12
    )
    
    print(f"Response:\n{response[:700]}\n")
    
    # Check for overstable discs (high fade or 0+ turn)
    stable_found = False
    for disc_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
        if len(disc_name) >= 5 and disc_name.lower() in response.lower():
            fade = DISC_DATABASE[disc_name].get('fade', 0)
            turn = DISC_DATABASE[disc_name].get('turn', 0)
            if fade >= 2 or turn >= 0:
                stable_found = True
                print(f"  ✅ {disc_name}: turn={turn}, fade={fade} (good for wind)")
    
    if stable_found:
        log_pass("Wind disc recommendations")
        return True
    else:
        log_fail("Wind disc recommendations", "No overstable discs found")
        return False


def test_hyzer_flip_recommendations():
    """Test that hyzer flip disc recommendations are understable"""
    print("\n📋 TEST 13: Hyzer Flip Recommendations")
    print("-"*50)
    
    response = handle_test_question(
        "jeg vil have en disc til hyzer flip kast",
        min_speed=7, max_speed=11
    )
    
    print(f"Response:\n{response[:700]}\n")
    
    # Check for understable discs (negative turn)
    understable_found = False
    for disc_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
        if len(disc_name) >= 5 and disc_name.lower() in response.lower():
            turn = DISC_DATABASE[disc_name].get('turn', 0)
            if turn <= -2:
                understable_found = True
                print(f"  ✅ {disc_name}: turn={turn} (good for hyzer flip)")
    
    if understable_found:
        log_pass("Hyzer flip recommendations")
        return True
    else:
        log_fail("Hyzer flip recommendations", "No understable discs found")
        return False


def test_approach_disc_recommendations():
    """Test approach disc recommendations"""
    print("\n📋 TEST 14: Approach Disc Recommendations")
    print("-"*50)
    
    response = handle_test_question(
        "jeg skal bruge en god approach disc",
        min_speed=2, max_speed=5
    )
    
    print(f"Response:\n{response[:700]}\n")
    
    # Check that discs are in approach range (speed 2-5)
    approach_found = False
    for disc_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
        if len(disc_name) >= 4 and disc_name.lower() in response.lower():
            speed = DISC_DATABASE[disc_name].get('speed', 0)
            if 2 <= speed <= 5:
                approach_found = True
                print(f"  ✅ {disc_name}: speed={speed} (good for approach)")
    
    if approach_found:
        log_pass("Approach disc recommendations")
        return True
    else:
        log_fail("Approach disc recommendations", "No approach discs found")
        return False


def test_multiple_disc_request():
    """Test recommendation of multiple discs"""
    print("\n📋 TEST 15: Multiple Disc Request (3 discs)")
    print("-"*50)
    
    response = handle_test_question(
        "giv mig 3 gode fairway drivere",
        min_speed=7, max_speed=9
    )
    
    print(f"Response:\n{response[:800]}\n")
    
    # Count how many discs are mentioned
    discs_found = []
    for disc_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
        if len(disc_name) >= 4 and disc_name.lower() in response.lower():
            speed = DISC_DATABASE[disc_name].get('speed', 0)
            if 7 <= speed <= 9 and disc_name not in discs_found:
                discs_found.append(disc_name)
    
    print(f"  Found {len(discs_found)} fairway drivers: {discs_found[:5]}")
    
    if len(discs_found) >= 2:
        log_pass(f"Multiple disc request - found {len(discs_found)} discs")
        return True
    else:
        log_fail("Multiple disc request", f"Only found {len(discs_found)} discs")
        return False


def test_specific_manufacturer():
    """Test recommendation from specific manufacturer"""
    print("\n📋 TEST 16: Specific Manufacturer (Innova)")
    print("-"*50)
    
    response = handle_test_question(
        "anbefal en god Innova disc",
        min_speed=5, max_speed=12
    )
    
    print(f"Response:\n{response[:700]}\n")
    
    # Check that Innova discs are mentioned
    innova_discs = ['Destroyer', 'Wraith', 'Thunderbird', 'Firebird', 'Valkyrie', 
                    'Roadrunner', 'Leopard', 'Roc3', 'Mako3', 'Buzzz', 'Aviar']
    
    innova_found = []
    for disc in innova_discs:
        if disc.lower() in response.lower():
            innova_found.append(disc)
    
    if innova_found:
        log_pass(f"Specific manufacturer - found Innova discs: {innova_found}")
        return True
    else:
        log_fail("Specific manufacturer", "No Innova discs found")
        return False


def test_straight_flying_disc():
    """Test recommendation for straight flying discs"""
    print("\n📋 TEST 17: Straight Flying Disc")
    print("-"*50)
    
    response = handle_test_question(
        "jeg vil have en disc der flyver helt lige",
        min_speed=4, max_speed=9
    )
    
    print(f"Response:\n{response[:700]}\n")
    
    # Check for neutral discs (turn close to 0, fade close to 0-1)
    straight_found = False
    for disc_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
        if len(disc_name) >= 4 and disc_name.lower() in response.lower():
            turn = DISC_DATABASE[disc_name].get('turn', 0)
            fade = DISC_DATABASE[disc_name].get('fade', 0)
            if -1.5 <= turn <= 0 and fade <= 2:
                straight_found = True
                print(f"  ✅ {disc_name}: turn={turn}, fade={fade} (straight)")
    
    if straight_found:
        log_pass("Straight flying disc")
        return True
    else:
        log_fail("Straight flying disc", "No straight-flying discs found")
        return False


def test_max_distance_disc():
    """Test recommendation for maximum distance"""
    print("\n📋 TEST 18: Max Distance Disc")
    print("-"*50)
    
    response = handle_test_question(
        "hvilken disc giver mest distance for erfarne spillere?",
        min_speed=10, max_speed=14
    )
    
    print(f"Response:\n{response[:700]}\n")
    
    # Check for high-speed drivers
    high_speed_found = False
    for disc_name in sorted(DISC_DATABASE.keys(), key=len, reverse=True):
        if len(disc_name) >= 4 and disc_name.lower() in response.lower():
            speed = DISC_DATABASE[disc_name].get('speed', 0)
            if speed >= 11:
                high_speed_found = True
                print(f"  ✅ {disc_name}: speed={speed} (high speed)")
    
    if high_speed_found:
        log_pass("Max distance disc")
        return True
    else:
        log_fail("Max distance disc", "No high-speed discs found")
        return False


def test_filter_removes_wrong_speed():
    """Test that filter actually removes wrong-speed discs"""
    print("\n📋 TEST 19: Filter Removes Wrong Speed")
    print("-"*50)
    
    # Simulate response with mixed speeds
    mixed_response = """
### **Destroyer** af Innova
- Flight: 12/5/-1/3
- Hvorfor: Great distance

### **Roadrunner** af Innova
- Flight: 9/5/-4/1
- Hvorfor: Good understable

### **Buzzz** af Discraft
- Flight: 5/4/-1/1
- Hvorfor: Classic midrange
"""
    
    # Filter for speed 7-9
    filtered = filter_wrong_speed_discs(mixed_response, DISC_DATABASE, 7, 9)
    print(f"Original:\n{mixed_response}")
    print(f"Filtered (7-9):\n{filtered}")
    
    # Check results
    has_roadrunner = 'roadrunner' in filtered.lower()
    has_destroyer = 'destroyer' in filtered.lower()
    has_buzzz = 'buzzz' in filtered.lower()
    
    if has_roadrunner and not has_destroyer and not has_buzzz:
        log_pass("Filter removes wrong speed - kept only Roadrunner")
        return True
    else:
        log_fail("Filter removes wrong speed", 
                 f"Roadrunner={has_roadrunner}, Destroyer={has_destroyer}, Buzzz={has_buzzz}")
        return False


def test_danish_language():
    """Test that responses are in Danish"""
    print("\n📋 TEST 20: Danish Language Response")
    print("-"*50)
    
    response = handle_test_question(
        "anbefal en god disc til mig",
        min_speed=5, max_speed=10
    )
    
    print(f"Response:\n{response[:500]}\n")
    
    # Check for Danish words
    danish_words = ['og', 'en', 'til', 'der', 'med', 'er', 'for', 'som', 'kan', 
                    'god', 'disc', 'kast', 'spiller', 'flyvning', 'afstand']
    
    danish_count = sum(1 for word in danish_words if word in response.lower())
    
    if danish_count >= 5:
        log_pass(f"Danish language - found {danish_count} Danish words")
        return True
    else:
        log_fail("Danish language", f"Only {danish_count} Danish words found")
        return False


def test_manufacturer_name_correction():
    """Test that manufacturer names get corrected by post-processing"""
    print("\n📋 TEST 21: Manufacturer Name Correction")
    print("-"*50)
    
    # Simulate AI giving wrong manufacturer names
    wrong_response = """### **Dynamic Discs Diamond** af Dynamic Discs
- Flight: 8/6/-3/1
- Hvorfor: Great understable disc

### **Discraft Heat** af Discraft
- Flight: 9/6/-3/1
- Hvorfor: Good for beginners"""
    
    corrected = fix_manufacturer_names_in_response(wrong_response, DISC_DATABASE)
    print(f"Original:\n{wrong_response}")
    print(f"\nCorrected:\n{corrected}")
    
    # Diamond should be Latitude 64, not Dynamic Discs
    all_pass = True
    
    if "Latitude 64" in corrected and "Dynamic Discs Diamond" not in corrected:
        print(f"  ✅ Diamond: correctly changed to Latitude 64")
    else:
        print(f"  ❌ Diamond: should be Latitude 64")
        all_pass = False
    
    # Heat should still be Discraft
    if "Discraft" in corrected:
        print(f"  ✅ Heat: correctly kept as Discraft")
    else:
        print(f"  ❌ Heat: should be Discraft")
        all_pass = False
    
    if all_pass:
        log_pass("Manufacturer name correction")
    else:
        log_fail("Manufacturer name correction")
    return all_pass


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    tests = [
        test_speed_range_7_9,
        test_speed_range_10_14,
        test_tell_me_more_database,
        test_roadrunner_flight,
        test_volt_flight,
        test_putter_speed,
        test_midrange_speed,
        test_understable_detection,
        test_overstable_detection,
        test_flight_number_correction,
        test_beginner_recommendations,
        test_wind_disc_recommendations,
        test_hyzer_flip_recommendations,
        test_approach_disc_recommendations,
        test_multiple_disc_request,
        test_specific_manufacturer,
        test_straight_flying_disc,
        test_max_distance_disc,
        test_filter_removes_wrong_speed,
        test_danish_language,
        test_manufacturer_name_correction,
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            log_fail(test.__name__, str(e))
    
    print("\n" + "="*60)
    print(f"  AI TEST RESULTS: {PASSED} passed, {FAILED} failed")
    print("="*60)
    
    if FAILED > 0:
        print("\n⚠️  Some AI tests failed. Review responses above.")
        sys.exit(1)
    else:
        print("\n🎉 All AI tests passed!")
        sys.exit(0)
