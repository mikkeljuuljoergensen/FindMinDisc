import requests


def check_disc_tree_stock(disc_name):
    """
    Check if a disc is in stock at Disc Tree using Shopify's suggest API.
    
    Returns dict with:
    - 'status': 'in_stock', 'sold_out', or 'not_found'
    - 'url': Direct link to product (if found)
    - 'price': Price in DKK (if found)
    - 'title': Full product name (if found)
    """
    try:
        # Use Shopify's suggest API
        search_url = f"https://disctree.dk/search/suggest.json?q={disc_name}&resources[type]=product&resources[limit]=10"
        response = requests.get(search_url, timeout=5)
        
        if response.status_code != 200:
            return {'status': 'not_found', 'url': None}
        
        data = response.json()
        products = data.get('resources', {}).get('results', {}).get('products', [])
        
        if not products:
            return {'status': 'not_found', 'url': None}
        
        # Look for exact disc name match (ignore plastic type variations)
        disc_lower = disc_name.lower()
        
        for product in products:
            title = product.get('title', '').lower()
            tags = product.get('tags', [])
            
            # Check if Mold_ tag matches the disc name
            mold_match = any(tag.lower() == f'mold_{disc_lower}' for tag in tags)
            
            # Or check if disc name is in title
            name_in_title = disc_lower in title
            
            if mold_match or name_in_title:
                available = product.get('available', False)
                product_url = f"https://disctree.dk{product.get('url', '').split('?')[0]}"
                price = product.get('price', '')
                
                return {
                    'status': 'in_stock' if available else 'sold_out',
                    'url': product_url,
                    'price': price,
                    'title': product.get('title', disc_name)
                }
        
        # No exact match found - disc not sold there
        return {'status': 'not_found', 'url': None}
        
    except Exception:
        # On error, return search URL as fallback
        return {
            'status': 'unknown',
            'url': f"https://disctree.dk/search?q={disc_name.replace(' ', '+')}"
        }


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