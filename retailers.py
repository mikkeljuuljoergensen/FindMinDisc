import requests


def get_product_links(disc_name):
    """
    Gets search links from Danish stores.
    NewDisc only sells Axiom, MVP, and Streamline discs.
    """
    links = {}
    
    # Disc Tree sells all brands
    links['Disc Tree'] = f"https://disctree.dk/search?q={disc_name.replace(' ', '+')}"
    
    # NewDisc only sells Axiom, MVP, Streamline
    mvp_axiom_streamline_discs = {
        # MVP
        'volt', 'reactor', 'relay', 'servo', 'resistor', 'wave', 'impulse', 'inertia',
        'photon', 'tesla', 'amp', 'anode', 'atom', 'ion', 'spin', 'proton', 'motion',
        'octane', 'catalyst', 'dimension', 'limit', 'shock', 'deflector', 'vertex',
        # Axiom
        'insanity', 'crave', 'envy', 'proxy', 'hex', 'paradox', 'pyro', 'fireball',
        'tenacity', 'excite', 'mayhem', 'tantrum', 'vanish', 'virus', 'wrath', 'clash',
        'defy', 'time-lapse', 'rhythm',
        # Streamline
        'pilot', 'drift', 'trace', 'flare', 'stabilizer', 'runway', 'ascend', 'lift'
    }
    
    if disc_name.lower() in mvp_axiom_streamline_discs:
        links['NewDisc'] = f"https://newdisc.dk/search?q={disc_name.replace(' ', '+')}*"
    
    return links