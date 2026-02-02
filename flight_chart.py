"""
Flight Chart Generator for Disc Golf
Reverse-engineered from DG Puttheads flight charts

Based on analysis of 1471 discs from https://flightcharts.dgputtheads.com/
"""

import math


def calculate_arm_speed_factor(user_distance_m, speed, glide):
    """
    Calculate continuous arm speed factor based on user's throwing distance.
    
    Args:
        user_distance_m: How far the user throws in meters
        speed: Disc speed rating
        glide: Disc glide rating
    
    Returns:
        dict with distance_mult and turn_mult
    """
    # Expected distance for this disc at "normal" arm speed
    expected_dist_ft = 180 + (speed * 18) + (glide * 8)
    expected_dist_m = expected_dist_ft * 0.3048
    
    # Calculate how much of the disc's potential the user achieves
    # This is the "arm speed factor" - ranges roughly 0.5 to 1.2
    arm_factor = user_distance_m / expected_dist_m
    
    # Clamp to reasonable range (0.5 = very slow, 1.2 = pro level)
    arm_factor = max(0.5, min(1.2, arm_factor))
    
    # Distance multiplier - linear relationship
    # arm_factor 0.7 → 0.89x, 1.0 → 1.0x, 1.2 → 1.05x
    # Based on data: slow=0.894x, fast=1.053x
    distance_mult = 0.7 + (arm_factor * 0.3)
    
    # Turn multiplier - more dramatic relationship!
    # Based on data: slow=0.62x, normal=1.0x, fast=2.15x
    # This is non-linear - faster arm speed dramatically increases turn
    if arm_factor <= 1.0:
        # Below normal: linear from 0.5 to 1.0
        # arm_factor 0.5 → 0.4, 0.7 → 0.6, 1.0 → 1.0
        turn_mult = 0.4 + (arm_factor * 0.6)
    else:
        # Above normal: accelerating curve
        # arm_factor 1.0 → 1.0, 1.2 → 1.8
        excess = arm_factor - 1.0
        turn_mult = 1.0 + (excess * 4.0)
    
    return {
        'arm_factor': arm_factor,
        'distance_mult': distance_mult,
        'turn_mult': turn_mult,
        'expected_dist_m': expected_dist_m
    }


def generate_flight_path(speed, glide, turn, fade, arm_speed='normal', throw='backhand', user_distance_m=None):
    """
    Generate flight path coordinates from flight numbers.
    
    Args:
        speed: Disc speed rating (1-14)
        glide: Disc glide rating (1-7)
        turn: Disc turn rating (-5 to +1)
        fade: Disc fade rating (0-5)
        arm_speed: 'slow', 'normal', 'fast' OR ignored if user_distance_m is provided
        throw: 'backhand' or 'forehand'
        user_distance_m: User's throwing distance in meters (enables precise calculation)
    
    Returns:
        List of {x, y} coordinates where:
        - y = distance in feet (0 to max)
        - x = lateral displacement (negative = right for RHBH)
    """
    # Use continuous calculation if user_distance_m is provided
    if user_distance_m is not None:
        factors = calculate_arm_speed_factor(user_distance_m, speed, glide)
        distance_mult = factors['distance_mult']
        turn_mult = factors['turn_mult']
        
        # Scale distance to match user's actual throwing distance
        # The path should end at approximately where the user would throw
        base_distance_ft = 180 + (speed * 18) + (glide * 8)
        target_distance_ft = user_distance_m / 0.3048
        distance = target_distance_ft
    else:
        # Legacy: use discrete arm speed categories
        arm_mults = {
            'slow':   {'dist': 0.88, 'turn': 0.62},
            'normal': {'dist': 1.00, 'turn': 1.00},
            'fast':   {'dist': 1.05, 'turn': 1.80}
        }
        mults = arm_mults.get(arm_speed, arm_mults['normal'])
        distance_mult = mults['dist']
        turn_mult = mults['turn']
        
        base_distance_ft = 180 + (speed * 18) + (glide * 8)
        distance = base_distance_ft * distance_mult
    
    # Forehand adjustment - more fade due to extra torque
    fade_mult = 1.18 if throw == 'forehand' else 1.0
    
    # Generate 18 points along the flight path
    points = []
    for i in range(18):
        t = i / 17  # 0 to 1
        
        # Y: Distance follows a decay curve (faster early, slower late)
        y = distance * (1 - (1 - t) ** 1.8)
        
        # X: Turn phase (high speed, early-mid flight)
        # Turn effect peaks around 60-70% of flight
        turn_effect = turn * 0.37 * turn_mult * math.sin(t * math.pi * 0.75)
        
        # X: Fade phase (low speed, late flight)
        # Fade kicks in after ~40% of flight and increases
        if t > 0.4:
            fade_t = (t - 0.4) / 0.6
            fade_effect = fade * fade_mult * 0.48 * fade_t ** 1.5
        else:
            fade_effect = 0
        
        x = turn_effect + fade_effect
        
        # Forehand: mirror x-axis
        if throw == 'forehand':
            x = -x
        
        points.append({'x': round(x, 3), 'y': round(y, 1)})
    
    return points


def get_flight_stats(speed, glide, turn, fade, arm_speed='normal', user_distance_m=None):
    """Get key flight statistics."""
    path = generate_flight_path(speed, glide, turn, fade, arm_speed, user_distance_m=user_distance_m)
    
    max_distance = path[-1]['y']
    max_turn = min(p['x'] for p in path)
    final_x = path[-1]['x']
    fade_amount = final_x - max_turn
    
    result = {
        'max_distance_ft': max_distance,
        'max_distance_m': round(max_distance * 0.3048, 1),
        'max_turn': max_turn,
        'final_position': final_x,
        'fade_amount': fade_amount
    }
    
    # Add arm speed info if using continuous calculation
    if user_distance_m is not None:
        factors = calculate_arm_speed_factor(user_distance_m, speed, glide)
        result['arm_factor'] = factors['arm_factor']
        result['turn_mult'] = factors['turn_mult']
        result['expected_dist_m'] = factors['expected_dist_m']
    
    return result


def estimate_required_arm_speed(speed):
    """
    Estimate the minimum throwing distance needed to properly throw a disc.
    
    Rule of thumb: ~10 meters per speed rating
    """
    return {
        'min_distance_m': speed * 10,
        'recommended_distance_m': speed * 12,
        'description': f"Speed {speed} disc kræver ca. {speed * 10}-{speed * 12}m kastelængde"
    }


def compare_arm_speeds(speed, glide, turn, fade):
    """Compare flight paths at different arm speeds."""
    return {
        'slow': generate_flight_path(speed, glide, turn, fade, 'slow'),
        'normal': generate_flight_path(speed, glide, turn, fade, 'normal'),
        'fast': generate_flight_path(speed, glide, turn, fade, 'fast')
    }


# Flight number explanations for users
FLIGHT_NUMBER_GUIDE = """
**Speed** (1-14): Discens aerodynamik. Højere = bredere kant = kræver mere armhastighed.
- Speed 1-3: Puttere - kan kastes af alle
- Speed 4-6: Midranges - kræver 40-60m kast
- Speed 7-9: Fairway drivers - kræver 60-80m kast  
- Speed 10-14: Distance drivers - kræver 80-120m+ kast

**Glide** (1-7): Evnen til at blive i luften. Højere = mere glide.
- Glide 1-2: Falder hurtigt, god til præcision
- Glide 5-6: Bliver længe i luften

**Turn** (-5 til +1): Tidlig flyvning (ved høj hastighed).
- Negativ (-1 til -5): Understabil, drejer HØJRE (for RHBH)
- 0 eller +1: Stabil/overstabil, går lige eller venstre

**Fade** (0-5): Sen flyvning (når hastigheden falder).
- 0-1: Lander lige
- 3-5: Hooker hårdt til VENSTRE til sidst
"""
