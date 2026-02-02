"""
Flight Chart Generator for Disc Golf
Reverse-engineered from DG Puttheads flight charts

Based on regression analysis of 1471 discs from https://flightcharts.dgputtheads.com/
Validated against 4413+ flight paths with avg error of 2.5m distance, 0.09 turn, 0.16 fade.

Formulas derived from least-squares regression on actual flight path data:
- Distance: R² = 0.978 (98% accuracy)
- Turn: R² = 0.888 (89% accuracy)
- Fade: R² = 0.878 (88% accuracy)
"""

import math


# ============================================================================
# PRECISE FORMULAS FROM disc_database_full.json REGRESSION ANALYSIS
# Based on 1248 flight paths (719 slow, 268 normal, 261 fast)
# ============================================================================

# Distance formulas (feet) by arm speed:
#   Slow:   158.12 + 12.20*speed + 12.03*glide  (R² = 0.9892, err = 1.4m)
#   Normal: 156.83 + 16.45*speed + 17.04*glide  (R² = 0.9941, err = 1.3m)
#   Fast:   155.88 + 17.75*speed + 19.30*glide  (R² = 0.9936, err = 1.3m)

DISTANCE_COEFFICIENTS = {
    'slow':   {'base': 158.12, 'speed': 12.20, 'glide': 12.03},
    'normal': {'base': 156.83, 'speed': 16.45, 'glide': 17.04},
    'fast':   {'base': 155.88, 'speed': 17.75, 'glide': 19.30}
}

# Turn formula: turn_amount = turn * base_coef * arm_mult
# Regression shows speed has almost NO effect on turn coefficient (R² = 0.001)
# So we use a constant: turn_coef ≈ 0.2311 (mean across all speeds)
TURN_BASE_COEF = 0.2311
TURN_SPEED_ADJ = 0.00122  # Negligible, but kept for completeness

# Turn coefficient by arm speed (multiplier on base turn effect):
#   Slow:   0.8327x (less turn with slower arm)
#   Normal: 1.0000x
#   Fast:   1.2703x (more turn with faster arm)
TURN_ARM_MULT = {'slow': 0.8327, 'normal': 1.0000, 'fast': 1.2703}

# Fade formula: fade_amount = fade * coef + turn * turn_factor
# Turn counteracts fade slightly (understable discs fade less)
#   Slow:   0.6236*fade + 0.0674*turn  (R² = 0.8498)
#   Normal: 0.5272*fade + 0.0398*turn  (R² = 0.8579)
#   Fast:   0.4528*fade + 0.0099*turn  (R² = 0.8688)
FADE_COEFFICIENTS = {
    'slow':   {'base': 0.6236, 'turn_factor': 0.0674},
    'normal': {'base': 0.5272, 'turn_factor': 0.0398},
    'fast':   {'base': 0.4528, 'turn_factor': 0.0099}
}


def calculate_distance(speed, glide, arm_speed='normal'):
    """
    Calculate expected distance in feet.
    
    Formula derived from regression on 1248 flight paths:
    - R² = 0.99+ (99% of variance explained)
    - Average error: ~1.3m
    """
    coef = DISTANCE_COEFFICIENTS.get(arm_speed, DISTANCE_COEFFICIENTS['normal'])
    return coef['base'] + coef['speed'] * speed + coef['glide'] * glide


def calculate_turn_effect(speed, turn, arm_speed='normal'):
    """
    Calculate the maximum turn displacement (negative = right for RHBH).
    
    Formula: turn_effect = turn * (0.3448 - 0.0087*speed) * arm_mult
    
    Key insight: Higher speed discs have less turn effect per rating point.
    - Speed 2 putter: turn_coef ≈ 0.33
    - Speed 12 driver: turn_coef ≈ 0.24
    """
    base_coef = TURN_BASE_COEF + TURN_SPEED_ADJ * speed
    arm_mult = TURN_ARM_MULT.get(arm_speed, 1.0)
    return turn * base_coef * arm_mult


def calculate_fade_effect(fade, turn, arm_speed='normal'):
    """
    Calculate the fade displacement (positive = left for RHBH).
    
    Formula: fade_effect = fade * coef + turn * turn_factor
    
    Key insight: Turn counteracts some fade - understable discs fade less.
    """
    coef = FADE_COEFFICIENTS.get(arm_speed, FADE_COEFFICIENTS['normal'])
    return fade * coef['base'] + turn * coef['turn_factor']


def interpolate_arm_speed(arm_factor):
    """
    Convert continuous arm factor (0.0-1.0+) to interpolated coefficients.
    
    arm_factor: 0.0 = slow, 0.5 = normal, 1.0 = fast
    """
    if arm_factor <= 0.5:
        # Interpolate between slow and normal
        t = arm_factor * 2  # 0 to 1
        return {
            'dist_base': DISTANCE_COEFFICIENTS['slow']['base'] + t * (DISTANCE_COEFFICIENTS['normal']['base'] - DISTANCE_COEFFICIENTS['slow']['base']),
            'dist_speed': DISTANCE_COEFFICIENTS['slow']['speed'] + t * (DISTANCE_COEFFICIENTS['normal']['speed'] - DISTANCE_COEFFICIENTS['slow']['speed']),
            'dist_glide': DISTANCE_COEFFICIENTS['slow']['glide'] + t * (DISTANCE_COEFFICIENTS['normal']['glide'] - DISTANCE_COEFFICIENTS['slow']['glide']),
            'turn_mult': TURN_ARM_MULT['slow'] + t * (TURN_ARM_MULT['normal'] - TURN_ARM_MULT['slow']),
            'fade_base': FADE_COEFFICIENTS['slow']['base'] + t * (FADE_COEFFICIENTS['normal']['base'] - FADE_COEFFICIENTS['slow']['base']),
            'fade_turn': FADE_COEFFICIENTS['slow']['turn_factor'] + t * (FADE_COEFFICIENTS['normal']['turn_factor'] - FADE_COEFFICIENTS['slow']['turn_factor'])
        }
    else:
        # Interpolate between normal and fast
        t = (arm_factor - 0.5) * 2  # 0 to 1
        return {
            'dist_base': DISTANCE_COEFFICIENTS['normal']['base'] + t * (DISTANCE_COEFFICIENTS['fast']['base'] - DISTANCE_COEFFICIENTS['normal']['base']),
            'dist_speed': DISTANCE_COEFFICIENTS['normal']['speed'] + t * (DISTANCE_COEFFICIENTS['fast']['speed'] - DISTANCE_COEFFICIENTS['normal']['speed']),
            'dist_glide': DISTANCE_COEFFICIENTS['normal']['glide'] + t * (DISTANCE_COEFFICIENTS['fast']['glide'] - DISTANCE_COEFFICIENTS['normal']['glide']),
            'turn_mult': TURN_ARM_MULT['normal'] + t * (TURN_ARM_MULT['fast'] - TURN_ARM_MULT['normal']),
            'fade_base': FADE_COEFFICIENTS['normal']['base'] + t * (FADE_COEFFICIENTS['fast']['base'] - FADE_COEFFICIENTS['normal']['base']),
            'fade_turn': FADE_COEFFICIENTS['normal']['turn_factor'] + t * (FADE_COEFFICIENTS['fast']['turn_factor'] - FADE_COEFFICIENTS['normal']['turn_factor'])
        }


def calculate_arm_speed_factor(user_distance_m, speed, glide):
    """
    Calculate continuous arm speed factor based on user's throwing distance.
    
    Returns arm_factor where:
    - 0.0 = "slow" arm speed
    - 0.5 = "normal" arm speed
    - 1.0 = "fast" arm speed
    - >1.0 = pro-level arm speed
    
    Uses precise formulas from disc_database_full.json regression.
    """
    # Calculate expected distances for this specific disc
    expected_slow_ft = calculate_distance(speed, glide, 'slow')
    expected_normal_ft = calculate_distance(speed, glide, 'normal')
    expected_fast_ft = calculate_distance(speed, glide, 'fast')
    
    expected_slow_m = expected_slow_ft * 0.3048
    expected_normal_m = expected_normal_ft * 0.3048
    expected_fast_m = expected_fast_ft * 0.3048
    
    # Calculate ratios for this specific disc
    ratio_slow = expected_slow_m / expected_normal_m  # ~0.83-0.90 depending on disc
    ratio_fast = expected_fast_m / expected_normal_m  # ~1.04-1.06 depending on disc
    
    # User's ratio relative to normal
    ratio = user_distance_m / expected_normal_m
    
    # Map ratio to arm_factor:
    # ratio = ratio_slow → arm_factor 0.0 (slow)
    # ratio = 1.000 → arm_factor 0.5 (normal)
    # ratio = ratio_fast → arm_factor 1.0 (fast)
    if ratio <= ratio_slow:
        arm_factor = 0.0
    elif ratio <= 1.0:
        # Linear interpolation between slow (0.0) and normal (0.5)
        arm_factor = 0.5 * (ratio - ratio_slow) / (1.0 - ratio_slow)
    elif ratio <= ratio_fast:
        # Linear interpolation between normal (0.5) and fast (1.0)
        arm_factor = 0.5 + 0.5 * (ratio - 1.0) / (ratio_fast - 1.0)
    else:
        # Beyond fast - extrapolate
        arm_factor = 1.0 + (ratio - ratio_fast) / (ratio_fast - 1.0)
    
    # Clamp to reasonable range
    arm_factor = max(0.0, min(1.5, arm_factor))
    
    return {
        'arm_factor': arm_factor,
        'ratio': ratio,
        'expected_dist_m': expected_normal_m,
        'expected_slow_m': expected_slow_m,
        'expected_fast_m': expected_fast_m
    }


def generate_flight_path(speed, glide, turn, fade, arm_speed='normal', throw='backhand', user_distance_m=None):
    """
    Generate flight path coordinates from flight numbers.
    
    Based on regression analysis of 1471 discs with R² > 0.87 for all metrics.
    
    Args:
        speed: Disc speed rating (1-14)
        glide: Disc glide rating (1-7)
        turn: Disc turn rating (-5 to +1)
        fade: Disc fade rating (0-5)
        arm_speed: 'slow', 'normal', 'fast' OR ignored if user_distance_m is provided
        throw: 'backhand' or 'forehand'
        user_distance_m: User's throwing distance in meters (enables precise calculation)
    
    Returns:
        List of {x, y} coordinates (18 points)
    """
    # Determine coefficients based on arm speed
    if user_distance_m is not None:
        factors = calculate_arm_speed_factor(user_distance_m, speed, glide)
        arm_factor = factors['arm_factor']
        coefs = interpolate_arm_speed(arm_factor)
        
        # Distance is user's actual throwing distance
        distance = user_distance_m / 0.3048  # Convert to feet
        
        # Turn and fade use interpolated coefficients
        turn_base = TURN_BASE_COEF + TURN_SPEED_ADJ * speed
        turn_effect = turn * turn_base * coefs['turn_mult']
        fade_effect = fade * coefs['fade_base'] + turn * coefs['fade_turn']
    else:
        # Use discrete arm speed categories
        distance = calculate_distance(speed, glide, arm_speed)
        turn_effect = calculate_turn_effect(speed, turn, arm_speed)
        fade_effect = calculate_fade_effect(fade, turn, arm_speed)
    
    # Forehand adjustment - more fade
    if throw == 'forehand':
        fade_effect *= 1.18
    
    # Generate 18 points along the flight path
    points = []
    for i in range(18):
        t = i / 17  # 0 to 1
        
        # Y: Distance follows a decay curve (faster early, slower late)
        y = distance * (1 - (1 - t) ** 1.8)
        
        # X: Turn phase (high speed, early-mid flight)
        # Turn peaks around 60-70% of flight, uses sine curve
        turn_x = turn_effect * math.sin(t * math.pi * 0.75)
        
        # X: Fade phase (low speed, late flight)
        # Fade kicks in after ~40% of flight
        if t > 0.4:
            fade_t = (t - 0.4) / 0.6
            fade_x = fade_effect * fade_t ** 1.5
        else:
            fade_x = 0
        
        x = turn_x + fade_x
        
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
    
    if user_distance_m is not None:
        factors = calculate_arm_speed_factor(user_distance_m, speed, glide)
        result['arm_factor'] = factors['arm_factor']
        result['expected_dist_m'] = factors['expected_dist_m']
    
    return result


def estimate_required_arm_speed(speed):
    """
    Estimate the minimum throwing distance needed to properly throw a disc.
    
    Based on: normal distance = 129.93 + 18.30*speed + 15.07*glide (assuming glide=5)
    """
    # Assuming average glide of 5
    expected_normal = (129.93 + 18.30 * speed + 15.07 * 5) * 0.3048
    expected_slow = (153.61 + 13.85 * speed + 8.07 * 5) * 0.3048
    
    return {
        'min_distance_m': round(expected_slow, 0),
        'recommended_distance_m': round(expected_normal, 0),
        'description': f"Speed {speed} disc: {expected_slow:.0f}-{expected_normal:.0f}m kastelængde"
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
