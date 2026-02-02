"""
Simple Reddit scraper without API - scrapes public pages directly
No authentication needed!
"""

import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime


def scrape_reddit_simple(limit=100):
    """
    Scrape r/discgolf without Reddit API.
    Just reads public pages directly.
    """
    posts = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    print("Scraping r/discgolf (public, no API needed)...")
    
    # Scrape multiple pages and sorting methods for more data
    sort_methods = ['hot', 'top', 'new']
    
    for sort_method in sort_methods:
        print(f"\nScraping {sort_method} posts...")
        
        # Get multiple pages
        for page in range(5):  # 5 pages per sort method
            if sort_method == 'top':
                url = f'https://old.reddit.com/r/discgolf/top/?t=month&after=t3_{page * 25}' if page > 0 else 'https://old.reddit.com/r/discgolf/top/?t=month'
            else:
                url = f'https://old.reddit.com/r/discgolf/{sort_method}/?after=t3_{page * 25}' if page > 0 else f'https://old.reddit.com/r/discgolf/{sort_method}/'
    
            try:
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                time.sleep(2)  # Be nice to Reddit servers
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find all posts
                for thing in soup.find_all('div', class_='thing'):
                    try:
                        # Get post data
                        post_id = thing.get('data-fullname', '').replace('t3_', '')
                        if not post_id or any(p['id'] == post_id for p in posts):
                            continue  # Skip duplicates
                        
                        title_elem = thing.find('a', class_='title')
                        
                        if not title_elem:
                            continue
                        
                        title = title_elem.get_text(strip=True)
                        score_elem = thing.find('div', class_='score unvoted')
                        score = score_elem.get_text(strip=True) if score_elem else '0'
                        
                        # Try to convert score to int
                        try:
                            score = int(score)
                        except:
                            score = 0
                        
                        # Get selftext if available
                        selftext = ""
                        
                        post_data = {
                            'id': post_id,
                            'title': title,
                            'selftext': selftext,
                            'author': 'unknown',
                            'score': score,
                            'url': f'https://reddit.com{thing.get("data-permalink", "")}',
                            'created_utc': time.time(),
                            'num_comments': 0,
                            'subreddit': 'discgolf',
                            'link_flair_text': None,
                            'comments': []
                        }
                        
                        posts.append(post_data)
                        
                        if len(posts) >= limit:
                            break
                            
                    except Exception as e:
                        print(f"Error parsing post: {e}")
                        continue
                
                if len(posts) >= limit:
                    break
                
            except Exception as e:
                print(f"Error fetching page: {e}")
                continue
        
        if len(posts) >= limit:
            break
        
        print(f"Scraped {len(posts)} posts so far...")
    
    print(f"\nTotal scraped: {len(posts)} posts")
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
            
            if post['selftext']:
                f.write("CONTENT:\n")
                f.write(post['selftext'])
                f.write("\n\n")
    
    print(f"✅ Created text file: {filename}")


if __name__ == "__main__":
    print("=" * 80)
    print("SIMPLE REDDIT SCRAPER (No API needed!)")
    print("=" * 80)
    print()
    
    # Scrape posts (increased to 500 for more comprehensive data)
    posts = scrape_reddit_simple(limit=500)
    
    if posts:
        # Save to JSON
        save_to_file(posts)
        
        # Create text file
        create_text_file(posts)
        
        print("\n✅ Done! You can now use the Simple Text Knowledge Base")
        print("   (No embeddings needed)")
    else:
        print("\n⚠️  No posts were scraped. Check your internet connection.")
