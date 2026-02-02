"""
Reddit Scraper for Disc Golf Content
Collects posts, comments, and recommendations from disc golf subreddits
"""

import praw
import json
from datetime import datetime
from typing import List, Dict
import re


class RedditDiscGolfScraper:
    """Scraper for disc golf content from Reddit"""
    
    def __init__(self, client_id: str, client_secret: str, user_agent: str):
        """
        Initialize Reddit scraper with PRAW credentials.
        
        To get credentials:
        1. Go to https://www.reddit.com/prefs/apps
        2. Create an app (script type)
        3. Use client_id and client_secret
        
        Args:
            client_id: Reddit app client ID
            client_secret: Reddit app client secret
            user_agent: User agent string (e.g., "DiscGolfBot/1.0")
        """
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent
        )
        self.subreddits = ['discgolf', 'discexchange', 'discdyeing']
        
    def scrape_subreddit(self, subreddit_name: str, limit: int = 100, 
                        sort_by: str = 'hot') -> List[Dict]:
        """
        Scrape posts from a specific subreddit.
        
        Args:
            subreddit_name: Name of subreddit
            limit: Number of posts to scrape
            sort_by: 'hot', 'new', 'top', 'rising'
            
        Returns:
            List of post dictionaries with content
        """
        subreddit = self.reddit.subreddit(subreddit_name)
        posts = []
        
        # Get posts based on sort method
        if sort_by == 'hot':
            submissions = subreddit.hot(limit=limit)
        elif sort_by == 'new':
            submissions = subreddit.new(limit=limit)
        elif sort_by == 'top':
            submissions = subreddit.top(limit=limit, time_filter='all')
        else:
            submissions = subreddit.rising(limit=limit)
        
        for submission in submissions:
            # Skip stickied posts
            if submission.stickied:
                continue
                
            post_data = {
                'id': submission.id,
                'title': submission.title,
                'selftext': submission.selftext,
                'author': str(submission.author),
                'score': submission.score,
                'url': submission.url,
                'created_utc': submission.created_utc,
                'num_comments': submission.num_comments,
                'subreddit': subreddit_name,
                'link_flair_text': submission.link_flair_text,
                'comments': []
            }
            
            # Get top comments
            try:
                submission.comments.replace_more(limit=0)  # Remove "load more"
                for comment in submission.comments.list()[:20]:  # Top 20 comments
                    if isinstance(comment, praw.models.Comment):
                        comment_data = {
                            'author': str(comment.author),
                            'body': comment.body,
                            'score': comment.score
                        }
                        post_data['comments'].append(comment_data)
            except Exception as e:
                print(f"Error fetching comments for {submission.id}: {e}")
            
            posts.append(post_data)
        
        return posts
    
    def scrape_disc_recommendations(self, limit: int = 500) -> List[Dict]:
        """
        Scrape posts specifically about disc recommendations and reviews.
        
        Filters for posts with keywords like:
        - "recommend", "suggestion", "what disc"
        - "beginner disc", "best disc"
        - disc names and reviews
        
        Returns:
            List of relevant posts
        """
        all_posts = []
        
        # Keywords to filter relevant posts
        keywords = [
            'recommend', 'suggestion', 'beginner', 'what disc',
            'best disc', 'similar to', 'replacement for',
            'understable', 'overstable', 'flippy', 'stable',
            'putter', 'midrange', 'fairway', 'driver', 'distance',
            'form check', 'throwing', 'flight', 'speed', 'glide'
        ]
        
        for subreddit_name in self.subreddits:
            print(f"Scraping r/{subreddit_name}...")
            
            # Get hot and top posts
            posts = self.scrape_subreddit(subreddit_name, limit=limit//len(self.subreddits), sort_by='hot')
            
            # Filter relevant posts
            for post in posts:
                title_lower = post['title'].lower()
                text_lower = post['selftext'].lower()
                combined = title_lower + ' ' + text_lower
                
                # Check if post is relevant
                is_relevant = any(keyword in combined for keyword in keywords)
                
                if is_relevant:
                    all_posts.append(post)
        
        return all_posts
    
    def extract_disc_mentions(self, text: str) -> List[str]:
        """
        Extract disc names mentioned in text.
        Basic pattern matching - can be improved with disc database.
        
        Args:
            text: Text to search
            
        Returns:
            List of potential disc names
        """
        # Common disc manufacturers
        manufacturers = ['Innova', 'Discraft', 'Latitude 64', 'Dynamic Discs', 
                        'Westside', 'MVP', 'Axiom', 'Prodigy', 'Discmania',
                        'Kastaplast', 'Gateway', 'Streamline', 'Lone Star',
                        'Thought Space', 'RPM', 'DGA']
        
        disc_mentions = []
        
        # Pattern: Manufacturer + Disc Name
        for mfr in manufacturers:
            pattern = rf'{mfr}\s+([A-Z][a-z]+(?:\s+[A-Z0-9][a-z0-9]*)*)'
            matches = re.findall(pattern, text)
            disc_mentions.extend([f"{mfr} {match}" for match in matches])
        
        return list(set(disc_mentions))
    
    def save_to_file(self, posts: List[Dict], filename: str = 'reddit_discgolf_data.json'):
        """
        Save scraped posts to JSON file.
        
        Args:
            posts: List of post dictionaries
            filename: Output filename
        """
        data = {
            'scraped_at': datetime.now().isoformat(),
            'total_posts': len(posts),
            'posts': posts
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Saved {len(posts)} posts to {filename}")
    
    def create_knowledge_base_text(self, posts: List[Dict], 
                                   output_file: str = 'discgolf_knowledge.txt'):
        """
        Create a searchable text file from Reddit posts.
        Formats content for easy reading and searching.
        
        Args:
            posts: List of post dictionaries
            output_file: Output text filename
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("DISC GOLF KNOWLEDGE BASE - Reddit Community Content\n")
            f.write("=" * 80 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Posts: {len(posts)}\n")
            f.write("=" * 80 + "\n\n")
            
            for i, post in enumerate(posts, 1):
                f.write(f"\n{'=' * 80}\n")
                f.write(f"POST #{i} | Score: {post['score']} | Comments: {post['num_comments']}\n")
                f.write(f"Subreddit: r/{post['subreddit']}\n")
                f.write(f"{'=' * 80}\n")
                f.write(f"TITLE: {post['title']}\n\n")
                
                if post['selftext']:
                    f.write("CONTENT:\n")
                    f.write(post['selftext'])
                    f.write("\n\n")
                
                if post['comments']:
                    f.write(f"TOP COMMENTS ({len(post['comments'])}):\n")
                    f.write("-" * 80 + "\n")
                    for j, comment in enumerate(post['comments'][:10], 1):
                        f.write(f"\n[Comment {j}] by u/{comment['author']} (↑{comment['score']})\n")
                        f.write(comment['body'])
                        f.write("\n")
                    f.write("\n")
        
        print(f"Created knowledge base text file: {output_file}")


def main():
    """
    Example usage of the Reddit scraper.
    
    YOU NEED TO:
    1. Get Reddit API credentials from https://www.reddit.com/prefs/apps
    2. Replace the placeholder values below
    """
    
    # REPLACE THESE WITH YOUR REDDIT API CREDENTIALS
    CLIENT_ID = "your_client_id_here"
    CLIENT_SECRET = "your_client_secret_here"
    USER_AGENT = "DiscGolfBot/1.0 by YourUsername"
    
    if CLIENT_ID == "your_client_id_here":
        print("=" * 80)
        print("⚠️  SETUP REQUIRED!")
        print("=" * 80)
        print("To use this scraper, you need Reddit API credentials:")
        print()
        print("1. Go to: https://www.reddit.com/prefs/apps")
        print("2. Click 'Create App' or 'Create Another App'")
        print("3. Select 'script' as app type")
        print("4. Fill in name (e.g., 'DiscGolfBot') and redirect uri (use http://localhost:8080)")
        print("5. Copy your client_id (under app name) and client_secret")
        print("6. Update CLIENT_ID and CLIENT_SECRET in this file")
        print()
        print("Then run: python reddit_scraper.py")
        print("=" * 80)
        return
    
    # Initialize scraper
    scraper = RedditDiscGolfScraper(CLIENT_ID, CLIENT_SECRET, USER_AGENT)
    
    print("Starting Reddit scraper for disc golf content...")
    print("This may take a few minutes...\n")
    
    # Scrape disc golf recommendations and discussions
    posts = scraper.scrape_disc_recommendations(limit=500)
    
    print(f"\nFound {len(posts)} relevant posts")
    
    # Save to JSON
    scraper.save_to_file(posts, 'reddit_discgolf_data.json')
    
    # Create searchable text file
    scraper.create_knowledge_base_text(posts, 'discgolf_knowledge.txt')
    
    print("\n✅ Done! Created:")
    print("  - reddit_discgolf_data.json (structured data)")
    print("  - discgolf_knowledge.txt (searchable text)")
    print("\nYou can now use these files with the knowledge base system.")


if __name__ == "__main__":
    main()
