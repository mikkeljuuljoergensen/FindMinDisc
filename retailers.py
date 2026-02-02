import requests
from bs4 import BeautifulSoup

def check_stock_disctree(disc_name):
    """
    Checks DiscTree.dk for a specific disc.
    """
    search_query = disc_name.replace(" ", "+")
    url = f"https://disctree.dk/search?q={search_query}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return "⚠️ Could not connect to Disc Tree."

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for Shopify product classes
        results = soup.select('.product-card, .product-item, .grid-view-item, .card-wrapper')
        
        if results:
            return f"✅ **Found at Disc Tree:** [View Search Results]({url})"
        else:
            return f"❌ Not currently in stock at Disc Tree."
            
    except Exception as e:
        return f"⚠️ Error checking stock: {str(e)}"

def check_stock_newdisc(disc_name):
    search_query = disc_name.replace(" ", "+")
    url = f"https://newdisc.dk/search?q={search_query}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if "Ingen resultater" in response.text or "No results" in response.text:
            return "❌ Not currently in stock at NewDisc."
        
        return f"🔍 **Check NewDisc:** [View Search Results]({url})"
    except Exception as e:
        return f"⚠️ Error checking stock: {str(e)}"