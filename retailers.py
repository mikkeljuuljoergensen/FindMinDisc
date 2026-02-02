import requests
from bs4 import BeautifulSoup

def scrape_disctree(disc_name, plastic=None):
    """
    Scrapes DiscTree.dk for a specific disc and optional plastic type.
    Returns list of products found or None if nothing found.
    """
    search_term = f"{disc_name} {plastic}" if plastic else disc_name
    url = f"https://disctree.dk/search?q={search_term.replace(' ', '+')}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find product cards - Disc Tree uses Shopify
        products = []
        
        # Try different Shopify selectors
        product_cards = soup.select('.product-card, .product-item, .grid-product, .product, [class*="product"]')
        
        for card in product_cards[:3]:  # Max 3 products
            # Try to find title
            title_elem = card.select_one('.product-card__title, .product-title, .product__title, h3, h2, a[href*="/products/"]')
            if not title_elem:
                continue
                
            title = title_elem.get_text(strip=True)
            
            # Check if disc name is in title
            if disc_name.lower() not in title.lower():
                continue
            
            # Get link
            link_elem = card.select_one('a[href*="/products/"]') or title_elem if title_elem.name == 'a' else None
            if link_elem and link_elem.get('href'):
                href = link_elem.get('href')
                if not href.startswith('http'):
                    href = f"https://disctree.dk{href}"
                link = href
            else:
                link = url
            
            # Check if sold out
            sold_out = False
            sold_out_elem = card.select_one('.sold-out, .product-card__badge--sold-out, [class*="sold"], [class*="udsolgt"]')
            if sold_out_elem or 'udsolgt' in card.get_text().lower() or 'sold out' in card.get_text().lower():
                sold_out = True
            
            # Get price if available
            price_elem = card.select_one('.price, .product-price, .money, [class*="price"]')
            price = price_elem.get_text(strip=True) if price_elem else None
            
            products.append({
                'title': title,
                'link': link,
                'sold_out': sold_out,
                'price': price,
                'store': 'Disc Tree'
            })
        
        return products if products else None
        
    except Exception as e:
        return None


def scrape_newdisc(disc_name, plastic=None):
    """
    Scrapes NewDisc.dk for a specific disc and optional plastic type.
    Returns list of products found or None if nothing found.
    """
    search_term = f"{disc_name} {plastic}" if plastic else disc_name
    url = f"https://newdisc.dk/search?q={search_term.replace(' ', '+')}"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
        
        # Check for no results
        if "Ingen resultater" in response.text or "No results" in response.text or "0 produkter" in response.text:
            return None
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        products = []
        product_cards = soup.select('.product-card, .product-item, .grid-product, .product, [class*="product"]')
        
        for card in product_cards[:3]:
            title_elem = card.select_one('.product-card__title, .product-title, .product__title, h3, h2, a[href*="/products/"]')
            if not title_elem:
                continue
                
            title = title_elem.get_text(strip=True)
            
            if disc_name.lower() not in title.lower():
                continue
            
            link_elem = card.select_one('a[href*="/products/"]') or title_elem if title_elem.name == 'a' else None
            if link_elem and link_elem.get('href'):
                href = link_elem.get('href')
                if not href.startswith('http'):
                    href = f"https://newdisc.dk{href}"
                link = href
            else:
                link = url
            
            sold_out = False
            sold_out_elem = card.select_one('.sold-out, .badge--sold-out, [class*="sold"], [class*="udsolgt"]')
            if sold_out_elem or 'udsolgt' in card.get_text().lower() or 'sold out' in card.get_text().lower():
                sold_out = True
            
            price_elem = card.select_one('.price, .product-price, .money, [class*="price"]')
            price = price_elem.get_text(strip=True) if price_elem else None
            
            products.append({
                'title': title,
                'link': link,
                'sold_out': sold_out,
                'price': price,
                'store': 'NewDisc'
            })
        
        return products if products else None
        
    except Exception as e:
        return None


def find_disc_in_stores(disc_name, plastic=None):
    """
    Searches both stores for a disc with optional plastic type.
    Returns formatted markdown string with results.
    """
    results = []
    
    # Search Disc Tree
    dt_products = scrape_disctree(disc_name, plastic)
    if dt_products:
        for p in dt_products[:1]:  # Take first match
            if p['sold_out']:
                results.append(f"❌ [{p['title']}]({p['link']}) - **Udsolgt** (Disc Tree)")
            else:
                price_str = f" - {p['price']}" if p['price'] else ""
                results.append(f"✅ [{p['title']}]({p['link']}){price_str} (Disc Tree)")
    
    # Search NewDisc
    nd_products = scrape_newdisc(disc_name, plastic)
    if nd_products:
        for p in nd_products[:1]:  # Take first match
            if p['sold_out']:
                results.append(f"❌ [{p['title']}]({p['link']}) - **Udsolgt** (NewDisc)")
            else:
                price_str = f" - {p['price']}" if p['price'] else ""
                results.append(f"✅ [{p['title']}]({p['link']}){price_str} (NewDisc)")
    
    return results


# Keep old functions for backwards compatibility but update them
def check_stock_disctree(disc_name):
    """Returns stock info or search link as fallback"""
    products = scrape_disctree(disc_name)
    search_url = f"https://disctree.dk/search?q={disc_name.replace(' ', '+')}"
    
    if products:
        p = products[0]
        if p['sold_out']:
            return f"❌ [Udsolgt]({p['link']})"
        return f"✅ [På lager]({p['link']})"
    # Always return search link as fallback
    return f"🔍 [Søg efter {disc_name}]({search_url})"


def check_stock_newdisc(disc_name):
    """Returns stock info or search link as fallback"""
    products = scrape_newdisc(disc_name)
    search_url = f"https://newdisc.dk/search?q={disc_name.replace(' ', '+')}"
    
    if products:
        p = products[0]
        if p['sold_out']:
            return f"❌ [Udsolgt]({p['link']})"
        return f"✅ [På lager]({p['link']})"
    # Always return search link as fallback
    return f"🔍 [Søg efter {disc_name}]({search_url})"