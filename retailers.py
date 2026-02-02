import requests
from bs4 import BeautifulSoup


def get_disctree_product(disc_name):
    """
    Uses Shopify suggest API to find direct product link on Disc Tree.
    Returns product URL or None.
    """
    try:
        url = f"https://disctree.dk/search/suggest.json?q={disc_name}&resources[type]=product&resources[limit]=3"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        products = data.get('resources', {}).get('results', {}).get('products', [])
        
        for product in products:
            title = product.get('title', '').lower()
            # Check if disc name is in product title
            if disc_name.lower() in title:
                product_url = product.get('url', '')
                if product_url:
                    # Clean URL and make absolute
                    clean_url = product_url.split('?')[0]
                    return f"https://disctree.dk{clean_url}"
        
        return None
    except Exception:
        return None


def get_newdisc_product(disc_name):
    """
    Uses Shopify suggest API to find direct product link on NewDisc.
    Returns product URL or None.
    """
    try:
        url = f"https://newdisc.dk/search/suggest.json?q={disc_name}&resources[type]=product&resources[limit]=3"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        products = data.get('resources', {}).get('results', {}).get('products', [])
        
        for product in products:
            title = product.get('title', '').lower()
            if disc_name.lower() in title:
                product_url = product.get('url', '')
                if product_url:
                    clean_url = product_url.split('?')[0]
                    return f"https://newdisc.dk{clean_url}"
        
        return None
    except Exception:
        return None


def get_product_links(disc_name):
    """
    Gets direct product links from Danish stores.
    Returns dict with store names and URLs.
    NewDisc only sells Axiom, MVP, and Streamline discs.
    """
    links = {}
    
    # Disc Tree sells all brands
    dt_url = get_disctree_product(disc_name)
    if dt_url:
        links['Disc Tree'] = dt_url
    else:
        links['Disc Tree'] = f"https://disctree.dk/search?q={disc_name.replace(' ', '+')}"
    
    # NewDisc only sells Axiom, MVP, Streamline - use wildcard search
    # Common discs from these brands:
    mvp_axiom_streamline_discs = {
        # MVP
        'volt', 'reactor', 'relay', 'servo', 'resistor', 'wave', 'impulse', 'inertia',
        'photon', 'tesla', 'amp', 'anode', 'atom', 'ion', 'spin', 'proton',
        # Axiom
        'insanity', 'crave', 'envy', 'proxy', 'hex', 'paradox', 'pyro', 'fireball',
        'tenacity', 'excite', 'mayhem', 'tantrum', 'vanish', 'virus', 'wrath',
        # Streamline
        'pilot', 'drift', 'trace', 'flare', 'stabilizer', 'runway', 'ascend', 'lift'
    }
    
    if disc_name.lower() in mvp_axiom_streamline_discs:
        links['NewDisc'] = f"https://newdisc.dk/search?q={disc_name.replace(' ', '+')}*"
    
    return links