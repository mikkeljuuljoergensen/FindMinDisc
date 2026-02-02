import requests
from urllib.parse import quote

def check_stock_disctree(disc_name):
    """
    Returns a search link for DiscTree.dk
    """
    search_query = quote(disc_name)
    url = f"https://disctree.dk/search?q={search_query}"
    return f"🔗 [Søg på Disc Tree]({url})"

def check_stock_newdisc(disc_name):
    """
    Returns a search link for NewDisc.dk
    """
    search_query = quote(disc_name)
    url = f"https://newdisc.dk/search?q={search_query}"
    return f"🔗 [Søg på NewDisc]({url})"

def check_stock_discimport(disc_name):
    """
    Returns a search link for DiscImport.dk
    """
    search_query = quote(disc_name)
    url = f"https://discimport.dk/search?q={search_query}"
    return f"🔗 [Søg på DiscImport]({url})"