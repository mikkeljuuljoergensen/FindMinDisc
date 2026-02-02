import requests

def check_stock_disctree(disc_name):
    """
    Returns a direct search link for DiscTree.dk
    """
    url = f"https://disctree.dk/search?q={disc_name}"
    return f"[Disc Tree]({url})"

def check_stock_newdisc(disc_name):
    """
    Returns a direct search link for NewDisc.dk
    """
    url = f"https://newdisc.dk/search?q={disc_name}"
    return f"[NewDisc]({url})"

def check_stock_discimport(disc_name):
    """
    Returns a direct search link for DiscImport.dk
    """
    url = f"https://discimport.dk/search?q={disc_name}"
    return f"[DiscImport]({url})"