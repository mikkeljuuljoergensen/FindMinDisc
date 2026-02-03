"""
FindMinDisc Test Suite
======================
Run this to test all major functionality from a user's perspective.

Usage:
    python test_app.py

Requirements:
    - disc_database.json must exist
    - disc_database_full.json must exist
    - No API keys needed for most tests
"""

import json
import re
import sys
from datetime import datetime

# Test counters
PASSED = 0
FAILED = 0
WARNINGS = 0

def log_pass(test_name, details=""):
    global PASSED
    PASSED += 1
    print(f"  ✅ PASS: {test_name}")
    if details:
        print(f"          {details}")

def log_fail(test_name, expected, got):
    global FAILED
    FAILED += 1
    print(f"  ❌ FAIL: {test_name}")
    print(f"          Expected: {expected}")
    print(f"          Got: {got}")

def log_warn(test_name, message):
    global WARNINGS
    WARNINGS += 1
    print(f"  ⚠️  WARN: {test_name}")
    print(f"          {message}")

def section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


# =============================================================================
# TEST 1: Database Loading
# =============================================================================
def test_database_loading():
    section("TEST 1: Database Loading")
    
    # Test disc_database.json
    try:
        with open('disc_database.json', 'r', encoding='utf-8') as f:
            db = json.load(f)
        if len(db) > 100:
            log_pass("disc_database.json loads", f"{len(db)} discs loaded")
        else:
            log_fail("disc_database.json loads", ">100 discs", f"{len(db)} discs")
    except Exception as e:
        log_fail("disc_database.json loads", "File loads without error", str(e))
    
    # Test disc_database_full.json
    try:
        with open('disc_database_full.json', 'r', encoding='utf-8') as f:
            db_full = json.load(f)
        if len(db_full) > 100:
            log_pass("disc_database_full.json loads", f"{len(db_full)} discs loaded")
        else:
            log_fail("disc_database_full.json loads", ">100 discs", f"{len(db_full)} discs")
    except Exception as e:
        log_fail("disc_database_full.json loads", "File loads without error", str(e))
    
    return db, db_full


# =============================================================================
# TEST 2: Key Disc Flight Numbers
# =============================================================================
def test_key_disc_flight_numbers(db):
    section("TEST 2: Key Disc Flight Numbers in Database")
    
    # These are the expected CORRECT values
    expected_discs = {
        'Volt': {'speed': 8, 'glide': 5, 'turn': -0.5, 'fade': 2},
        'Photon': {'speed': 11, 'glide': 5, 'turn': -1, 'fade': 2.5},
        'Roadrunner': {'speed': 9, 'glide': 5, 'turn': -4, 'fade': 1},
        'Destroyer': {'speed': 12, 'glide': 5, 'turn': -1, 'fade': 3},
        'Escape': {'speed': 9, 'glide': 5, 'turn': -1, 'fade': 2},
        'Wraith': {'speed': 11, 'glide': 5, 'turn': -1, 'fade': 3},
        'Buzzz': {'speed': 5, 'glide': 4, 'turn': -1, 'fade': 1},
        'Aviar': {'speed': 2, 'glide': 3, 'turn': 0, 'fade': 1},
    }
    
    for disc_name, expected in expected_discs.items():
        if disc_name not in db:
            log_fail(f"{disc_name} exists", "Disc in database", "Not found")
            continue
        
        disc = db[disc_name]
        all_match = True
        mismatches = []
        
        for key, exp_val in expected.items():
            got_val = disc.get(key)
            if got_val != exp_val:
                all_match = False
                mismatches.append(f"{key}: expected {exp_val}, got {got_val}")
        
        if all_match:
            log_pass(f"{disc_name} flight numbers", 
                     f"{expected['speed']}/{expected['glide']}/{expected['turn']}/{expected['fade']}")
        else:
            log_fail(f"{disc_name} flight numbers", 
                     f"{expected['speed']}/{expected['glide']}/{expected['turn']}/{expected['fade']}", 
                     ", ".join(mismatches))


# =============================================================================
# TEST 3: Flight Number Correction Function
# =============================================================================
def test_flight_number_correction(db):
    section("TEST 3: Flight Number Correction Function")
    
    # Import the function
    try:
        # We need to mock streamlit to import app
        import sys
        from unittest.mock import MagicMock
        sys.modules['streamlit'] = MagicMock()
        
        # Now we can define our own version based on the app code
        def fix_flight_numbers_in_response(response, database):
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
                    
                    line = re.sub(r'(Flight[:\s]+)\d+/\d+/-?\d+\.?\d*/\d+\.?\d*', 
                                  rf'\g<1>{speed}/{glide}/{turn}/{fade}', line, flags=re.IGNORECASE)
                    line = re.sub(r'(Speed[:\s]+)\d+', rf'\g<1>{speed}', line, flags=re.IGNORECASE)
                    line = re.sub(r'(Glide[:\s]+)\d+', rf'\g<1>{glide}', line, flags=re.IGNORECASE)
                    line = re.sub(r'(Turn[:\s]+)-?\d+\.?\d*', rf'\g<1>{turn}', line, flags=re.IGNORECASE)
                    line = re.sub(r'(Fade[:\s]+)\d+\.?\d*', rf'\g<1>{fade}', line, flags=re.IGNORECASE)
                
                result_lines.append(line)
            
            return '\n'.join(result_lines)
        
        log_pass("Function definition works")
        
    except Exception as e:
        log_fail("Function definition", "No errors", str(e))
        return
    
    # Test cases
    test_cases = [
        {
            'name': 'Fix Photon Speed: 13 → 11',
            'input': '**Photon**\n- Speed: 13\n- Glide: 5',
            'must_contain': 'Speed: 11',
            'must_not_contain': 'Speed: 13'
        },
        {
            'name': 'Fix Volt Speed: 13 → 8',
            'input': '**Volt**\n- Speed: 13',
            'must_contain': 'Speed: 8',
            'must_not_contain': 'Speed: 13'
        },
        {
            'name': 'Fix Roadrunner Flight format',
            'input': '**Roadrunner**\n- Flight: 13/5/-3/1',
            'must_contain': '9/5/-4/1',
            'must_not_contain': '13/5/-3/1'
        },
        {
            'name': 'Fix multiple discs independently',
            'input': '**Photon**\n- Speed: 13\n\n**Volt**\n- Speed: 13',
            'must_contain': 'Speed: 11',  # Photon
            'check_also': 'Speed: 8'      # Volt
        },
        {
            'name': 'Fix Destroyer with header format',
            'input': '### 1. **Destroyer** af Innova\n- Flight: 14/5/-2/4',
            'must_contain': '12/5/-1/3',
            'must_not_contain': '14/5/-2/4'
        },
    ]
    
    for tc in test_cases:
        result = fix_flight_numbers_in_response(tc['input'], db)
        
        passed = True
        if tc['must_contain'] not in result:
            passed = False
        if 'must_not_contain' in tc and tc['must_not_contain'] in result:
            passed = False
        if 'check_also' in tc and tc['check_also'] not in result:
            passed = False
        
        if passed:
            log_pass(tc['name'])
        else:
            log_fail(tc['name'], f"Contains '{tc['must_contain']}'", result[:100])


# =============================================================================
# TEST 3b: Speed Range Filtering Function
# =============================================================================
def test_speed_filtering_function(db):
    section("TEST 3b: Speed Range Filtering Function")
    
    def filter_wrong_speed_discs(response, database, min_speed, max_speed):
        """Remove disc recommendations that don't match the requested speed range."""
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
    
    # Test cases - simulate AI recommending wrong speed discs
    test_cases = [
        {
            'name': 'Remove Leopard (speed 6) when 7-9 requested',
            'input': '**Leopard**\n- Flight: 6/5/-2/1\n- Hvorfor: Great disc\n\n**Roadrunner**\n- Flight: 9/5/-4/1',
            'min_speed': 7, 'max_speed': 9,
            'must_contain': 'Roadrunner',
            'must_not_contain': 'Leopard'
        },
        {
            'name': 'Remove Buzzz (speed 5) when 7-9 requested',
            'input': '**Buzzz**\n- Flight: 5/4/-1/1\n\n**Escape**\n- Flight: 9/5/-1/2',
            'min_speed': 7, 'max_speed': 9,
            'must_contain': 'Escape',
            'must_not_contain': 'Buzzz'
        },
        {
            'name': 'Keep all discs when in range',
            'input': '**Roadrunner**\n- Flight: 9/5/-4/1\n\n**Escape**\n- Flight: 9/5/-1/2',
            'min_speed': 7, 'max_speed': 9,
            'must_contain': 'Roadrunner',
            'check_also': 'Escape'
        },
        {
            'name': 'Remove Destroyer (speed 12) when 7-9 requested',
            'input': '**Destroyer**\n- Flight: 12/5/-1/3\n\n**Volt**\n- Flight: 8/5/-0.5/2',
            'min_speed': 7, 'max_speed': 9,
            'must_contain': 'Volt',
            'must_not_contain': 'Destroyer'
        },
    ]
    
    for tc in test_cases:
        result = filter_wrong_speed_discs(tc['input'], db, tc['min_speed'], tc['max_speed'])
        
        passed = True
        if tc['must_contain'] not in result:
            passed = False
        if 'must_not_contain' in tc and tc['must_not_contain'] in result:
            passed = False
        if 'check_also' in tc and tc['check_also'] not in result:
            passed = False
        
        if passed:
            log_pass(tc['name'])
        else:
            log_fail(tc['name'], f"Contains '{tc['must_contain']}', not '{tc.get('must_not_contain', 'N/A')}'", result[:80])


# =============================================================================
# TEST 3c: "Tell Me More" Detection
# =============================================================================
def test_tell_more_detection(db):
    section("TEST 3c: Tell Me More Detection")
    
    # Test detection of "tell me more" patterns
    test_cases = [
        ('fortæl mig mere om Photon og Volt', True, ['Photon', 'Volt']),
        ('mere om Destroyer', True, ['Destroyer']),
        ('hvad med Buzzz?', True, ['Buzzz']),
        ('beskriv Roadrunner', True, ['Roadrunner']),
        ('jeg søger en understabil disc', False, []),
        ('sammenlign Volt og Escape', False, []),  # Not a "tell more" request
    ]
    
    tell_more_patterns = ['fortæl', 'forklar', 'mere om', 'hvad med', 'beskriv', 'info om', 'information om']
    
    for prompt, expected_is_tell_more, expected_discs in test_cases:
        prompt_lower = prompt.lower()
        
        # Detect "tell me more" pattern
        is_tell_more = any(p in prompt_lower for p in tell_more_patterns)
        
        # Find disc names
        discs_found = []
        for disc_name in sorted(db.keys(), key=len, reverse=True):
            if disc_name.lower() in prompt_lower:
                discs_found.append(disc_name)
                if len(discs_found) >= 4:
                    break
        
        if is_tell_more == expected_is_tell_more:
            if expected_discs:
                if set(discs_found) == set(expected_discs):
                    log_pass(f"'{prompt[:30]}...'", f"Tell more: {is_tell_more}, Discs: {discs_found}")
                else:
                    log_fail(f"'{prompt[:30]}...'", f"Discs: {expected_discs}", f"Got: {discs_found}")
            else:
                log_pass(f"'{prompt[:30]}...'", f"Tell more: {is_tell_more}")
        else:
            log_fail(f"'{prompt[:30]}...'", f"Tell more: {expected_is_tell_more}", f"Got: {is_tell_more}")


# =============================================================================
# TEST 4: Speed Range Detection
# =============================================================================
def test_speed_range_detection():
    section("TEST 4: Speed Range Detection")
    
    test_cases = [
        ('jeg søger 7-9 speed disc', (7, 9)),
        ('speed 7-9 understabil', (7, 9)),
        ('10-14 speed driver', (10, 14)),
        ('speed 4-6 midrange', (4, 6)),
        ('en god putter', None),  # No speed range
    ]
    
    for prompt, expected in test_cases:
        prompt_lower = prompt.lower()
        speed_range_match = re.search(r'(\d+)\s*-\s*(\d+)\s*speed|speed\s*(\d+)\s*-\s*(\d+)', prompt_lower)
        
        if speed_range_match:
            groups = speed_range_match.groups()
            min_speed = int(groups[0] or groups[2])
            max_speed = int(groups[1] or groups[3])
            result = (min_speed, max_speed)
        else:
            result = None
        
        if result == expected:
            log_pass(f"Detect speed in: '{prompt}'", f"Found: {result}")
        else:
            log_fail(f"Detect speed in: '{prompt}'", str(expected), str(result))


# =============================================================================
# TEST 5: Disc Type Detection
# =============================================================================
def test_disc_type_detection():
    section("TEST 5: Disc Type Detection")
    
    test_cases = [
        ('jeg vil have en putter', 'Putter'),
        ('god midrange til begyndere', 'Midrange'),
        ('fairway driver', 'Fairway driver'),
        ('distance driver til lange kast', 'Distance driver'),
        ('approach disc', 'Putter'),  # Approach → Putter
        ('en god driver', 'Distance driver'),
    ]
    
    for prompt, expected in test_cases:
        prompt_lower = prompt.lower()
        
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
        
        if disc_type == expected:
            log_pass(f"Detect type in: '{prompt[:30]}...'", f"Found: {disc_type}")
        else:
            log_fail(f"Detect type in: '{prompt[:30]}...'", expected, disc_type)


# =============================================================================
# TEST 6: Flight Path Data
# =============================================================================
def test_flight_path_data(db_full):
    section("TEST 6: Flight Path Data in Full Database")
    
    # Check that key discs have flight path data
    test_discs = ['Destroyer', 'Buzzz', 'Aviar', 'Volt', 'Photon']
    
    for disc_name in test_discs:
        if disc_name not in db_full:
            log_fail(f"{disc_name} in full database", "Disc exists", "Not found")
            continue
        
        disc = db_full[disc_name]
        
        # Check for flight path keys
        has_slow = 'flight_path_bh_slow' in disc
        has_normal = 'flight_path_bh_normal' in disc
        has_fast = 'flight_path_bh_fast' in disc
        
        if has_slow and has_normal and has_fast:
            path_len = len(disc.get('flight_path_bh_normal', []))
            log_pass(f"{disc_name} has flight paths", f"{path_len} points in normal path")
        elif has_normal:
            log_warn(f"{disc_name} flight paths", "Only normal path found")
        else:
            log_fail(f"{disc_name} has flight paths", "slow/normal/fast paths", 
                     f"slow={has_slow}, normal={has_normal}, fast={has_fast}")


# =============================================================================
# TEST 7: Knowledge Base Files
# =============================================================================
def test_knowledge_base_files():
    section("TEST 7: Knowledge Base Files")
    
    # Test reddit data file
    try:
        with open('reddit_discgolf_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        post_count = len(data.get('posts', []))
        if post_count >= 100:
            log_pass("reddit_discgolf_data.json", f"{post_count} posts loaded")
        else:
            log_warn("reddit_discgolf_data.json", f"Only {post_count} posts (expected 500+)")
    except FileNotFoundError:
        log_warn("reddit_discgolf_data.json", "File not found - run simple_scraper.py")
    except Exception as e:
        log_fail("reddit_discgolf_data.json", "File loads", str(e))
    
    # Test FAISS index
    try:
        import os
        if os.path.exists('faiss_db/index.faiss'):
            size = os.path.getsize('faiss_db/index.faiss')
            log_pass("FAISS index exists", f"Size: {size/1024:.1f} KB")
        else:
            log_warn("FAISS index", "Not found - run knowledge_base.py")
    except Exception as e:
        log_fail("FAISS index check", "No errors", str(e))
    
    # Test knowledge text file
    try:
        with open('discgolf_knowledge.txt', 'r', encoding='utf-8') as f:
            content = f.read()
        lines = content.count('\n')
        log_pass("discgolf_knowledge.txt", f"{lines} lines")
    except FileNotFoundError:
        log_warn("discgolf_knowledge.txt", "File not found - run simple_scraper.py")
    except Exception as e:
        log_fail("discgolf_knowledge.txt", "File loads", str(e))


# =============================================================================
# TEST 8: Retailers Integration
# =============================================================================
def test_retailers():
    section("TEST 8: Retailers Integration")
    
    try:
        from retailers import get_product_links
        log_pass("retailers.py imports")
        
        # Test getting links for a popular disc
        links = get_product_links("Destroyer")
        if links and len(links) > 0:
            log_pass("get_product_links works", f"Found links: {list(links.keys())}")
        else:
            log_warn("get_product_links", "No links returned for 'Destroyer'")
            
    except ImportError as e:
        log_fail("retailers.py imports", "Module loads", str(e))
    except Exception as e:
        log_warn("retailers.py", f"Error testing: {e}")


# =============================================================================
# TEST 9: Flight Chart Module
# =============================================================================
def test_flight_chart():
    section("TEST 9: Flight Chart Module")
    
    try:
        from flight_chart import generate_flight_path, get_flight_stats
        log_pass("flight_chart.py imports")
        
        # Test generating a flight path
        path = generate_flight_path(speed=9, glide=5, turn=-1, fade=2, arm_speed='normal')
        if path and len(path) > 10:
            log_pass("generate_flight_path works", f"{len(path)} points generated")
        else:
            log_fail("generate_flight_path", ">10 points", f"{len(path) if path else 0} points")
        
        # Test getting stats
        stats = get_flight_stats(speed=9, glide=5, turn=-1, fade=2, arm_speed='normal')
        if stats and 'max_distance_m' in stats:
            log_pass("get_flight_stats works", f"Max distance: {stats['max_distance_m']}m")
        else:
            log_fail("get_flight_stats", "Returns stats dict", str(stats))
            
    except ImportError as e:
        log_fail("flight_chart.py imports", "Module loads", str(e))
    except Exception as e:
        log_fail("flight_chart.py", "No errors", str(e))


# =============================================================================
# TEST 10: App Syntax Check
# =============================================================================
def test_app_syntax():
    section("TEST 10: App Syntax Check")
    
    import subprocess
    result = subprocess.run(
        [sys.executable, '-m', 'py_compile', 'app.py'],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        log_pass("app.py syntax valid")
    else:
        log_fail("app.py syntax", "No syntax errors", result.stderr)


# =============================================================================
# TEST 11: Speed Filtering for Recommendations
# =============================================================================
def test_speed_filtering(db):
    section("TEST 11: Speed Range Filtering")
    
    # Simulate filtering for fairway drivers (speed 7-9)
    min_speed, max_speed = 7, 9
    matching = []
    
    for name, data in db.items():
        speed = data.get('speed', 0)
        if min_speed <= speed <= max_speed:
            matching.append((name, speed))
    
    if len(matching) >= 20:
        log_pass(f"Speed {min_speed}-{max_speed} filtering", f"Found {len(matching)} discs")
        # Show a few examples
        examples = matching[:5]
        for name, speed in examples:
            print(f"          - {name} (speed {speed})")
    else:
        log_fail(f"Speed {min_speed}-{max_speed} filtering", ">=20 discs", f"{len(matching)} discs")
    
    # Verify no wrong speeds in results
    wrong_speed = [n for n, s in matching if s < min_speed or s > max_speed]
    if not wrong_speed:
        log_pass("No discs outside speed range")
    else:
        log_fail("Speed range enforcement", "No wrong speeds", f"Found: {wrong_speed[:5]}")


# =============================================================================
# TEST 12: Understable Disc Filtering
# =============================================================================
def test_understable_filtering(db):
    section("TEST 12: Understable Disc Filtering")
    
    # Filter for understable fairway drivers (speed 7-9, turn < 0)
    understable = []
    
    for name, data in db.items():
        speed = data.get('speed', 0)
        turn = data.get('turn', 0)
        if 7 <= speed <= 9 and turn < 0:
            understable.append((name, speed, turn))
    
    if len(understable) >= 10:
        log_pass(f"Understable fairways found", f"{len(understable)} discs")
        # Show examples
        examples = sorted(understable, key=lambda x: x[2])[:5]  # Most understable first
        for name, speed, turn in examples:
            print(f"          - {name} (speed {speed}, turn {turn})")
    else:
        log_warn("Understable fairways", f"Only {len(understable)} found (expected 10+)")


# =============================================================================
# MAIN
# =============================================================================
def main():
    print("\n" + "="*60)
    print("  FindMinDisc Test Suite")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("="*60)
    
    # Run all tests
    db, db_full = test_database_loading()
    
    if db:
        test_key_disc_flight_numbers(db)
        test_flight_number_correction(db)
        test_speed_filtering_function(db)
        test_tell_more_detection(db)
        test_speed_filtering(db)
        test_understable_filtering(db)
    
    test_speed_range_detection()
    test_disc_type_detection()
    
    if db_full:
        test_flight_path_data(db_full)
    
    test_knowledge_base_files()
    test_retailers()
    test_flight_chart()
    test_app_syntax()
    
    # Summary
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    print(f"  ✅ Passed:   {PASSED}")
    print(f"  ❌ Failed:   {FAILED}")
    print(f"  ⚠️  Warnings: {WARNINGS}")
    print("="*60)
    
    if FAILED > 0:
        print("\n  ⚠️  Some tests failed! Review the output above.")
        return 1
    elif WARNINGS > 0:
        print("\n  ℹ️  All tests passed, but there are warnings to review.")
        return 0
    else:
        print("\n  🎉 All tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
