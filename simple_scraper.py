"""
Enhanced Reddit scraper without API - scrapes public pages directly
No authentication needed! Gets 500+ posts.
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime


def scrape_reddit_simple(limit=500):
    """
    Scrape r/discgolf without Reddit API.
    Just reads public pages directly.
    """
    posts = []
    seen_ids = set()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    print("Scraping r/discgolf for 500+ posts...\n")
    
    # Scrape multiple sorting methods and time filters
    scrape_configs = [
        ('hot', None, 20),
        ('new', None, 20),
        ('rising', None, 10),
        ('top', 'all', 15),
        ('top', 'year', 15),
        ('top', 'month', 10),
        ('top', 'week', 10),
    ]
    
    for sort_method, time_filter, max_pages in scrape_configs:
        if len(posts) >= limit:
            break
            
        print(f"{'='*70}")
        config_name = f"{sort_method}" + (f" ({time_filter})" if time_filter else "")
        print(f"Scraping {config_name}...")
        print(f"{'='*70}")
        
        after = None
        
        for page in range(max_pages):
            if len(posts) >= limit:
                break
            
            # Build URL
            if time_filter:
                url = f'https://old.reddit.com/r/discgolf/{sort_method}/?t={time_filter}'
            else:
                url = f'https://old.reddit.com/r/discgolf/{sort_method}/'
            
            if after:
                url += f'{"&" if "?" in url else "?"}after={after}'
            
            try:
                time.sleep(1.5)  # Rate limiting
                response = requests.get(url, headers=headers)
                
                if response.status_code != 200:
                    print(f"  ⚠ Page {page+1} failed (status {response.status_code})")
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Find all posts
                things = soup.find_all('div', class_='thing')
                if not things:
                    print(f"  ✓ No more posts on page {page+1}")
                    break
                
                page_count = 0
                for thing in things:
                    if len(posts) >= limit:
                        break
                        
                    post_id = thing.get('data-fullname')
                    if not post_id or post_id in seen_ids:
                        continue
                    
                    seen_ids.add(post_id)
                    
                    # Get title
                    title_elem = thing.find('a', class_='title')
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    
                    # Get score
                    score = thing.get('data-score', '0')
                    try:
                        score = int(score)
                    except:
                        score = 0
                    
                    # Get selftext if available
                    post_text = title
                    selftext_div = thing.find('div', class_='expando')
                    if selftext_div:
                        md_div = selftext_div.find('div', class_='md')
                        if md_div:
                            selftext = md_div.get_text(separator='\n', strip=True)
                            if selftext and len(selftext) > 10:
                                post_text += "\n\n" + selftext
                    
                    posts.append({
                        'id': post_id,
                        'title': title,
                        'text': post_text,
                        'url': 'https://reddit.com' + thing.get('data-permalink', ''),
                        'score': score,
                        'source': config_name
                    })
                    page_count += 1
                
                print(f"  ✓ Page {page+1}: +{page_count} posts | Total: {len(posts)}")
                
                # Get next page token
                next_button = soup.find('span', class_='next-button')
                if next_button:
                    next_link = next_button.find('a')
                    if next_link:
                        next_url = next_link.get('href', '')
                        if 'after=' in next_url:
                            after = next_url.split('after=')[1].split('&')[0]
                        else:
                            break
                    else:
                        break
                else:
                    break
                    
            except Exception as e:
                print(f"  ⚠ Error on page {page+1}: {str(e)}")
                break
    
    print(f"\n{'='*70}")
    print(f"✅ Total scraped: {len(posts)} unique posts")
    print(f"{'='*70}\n")
    return posts


def save_to_file(posts, filename='reddit_discgolf_data.json'):
    """Save posts to JSON file."""
    data = {
        'scraped_at': datetime.now().isoformat(),
        'total_posts': len(posts),
        'posts': posts
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved {len(posts)} posts to {filename}")


def create_text_file(posts, filename='discgolf_knowledge.txt'):
    """Create searchable text file."""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("DISC GOLF KNOWLEDGE BASE\n")
        f.write("=" * 80 + "\n")
        f.write(f"Scraped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total Posts: {len(posts)}\n")
        f.write("=" * 80 + "\n\n")
        
        for i, post in enumerate(posts, 1):
            f.write(f"\n{'=' * 80}\n")
            f.write(f"POST #{i} | Score: {post['score']}\n")
            f.write(f"{'=' * 80}\n")
            f.write(f"TITLE: {post['title']}\n\n")
            
            if post.get('text') and post['text'] != post['title']:
                f.write("CONTENT:\n")
                f.write(post['text'])
                f.write("\n\n")
            
            f.write(f"URL: {post['url']}\n")
            f.write(f"Source: {post.get('source', 'unknown')}\n")
    
    print(f"✅ Saved knowledge base to {filename}")


if __name__ == "__main__":
    # Scrape posts
    posts = scrape_reddit_simple(limit=500)
    
    # Save to files
    save_to_file(posts)
    create_text_file(posts)
    
    print("\n✨ Done! Now run: python knowledge_base.py")
