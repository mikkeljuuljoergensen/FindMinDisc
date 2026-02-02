"""
Knowledge Base System with Semantic Search
Uses embeddings and vector similarity for intelligent content retrieval
"""

import json
import os
import pickle
from typing import List, Dict, Optional
import numpy as np
import faiss
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from datetime import datetime


class DiscGolfKnowledgeBase:
    """
    Knowledge base system for disc golf content with semantic search.
    Uses FAISS for vector storage and OpenAI embeddings.
    """
    
    def __init__(self, db_path: str = "./faiss_db", openai_api_key: Optional[str] = None):
        """
        Initialize knowledge base.
        
        Args:
            db_path: Path to FAISS storage directory
            openai_api_key: OpenAI API key (uses env var if None)
        """
        self.db_path = db_path
        os.makedirs(db_path, exist_ok=True)
        
        # Initialize embeddings with explicit API key
        if openai_api_key is None:
            openai_api_key = os.getenv('OPENAI_API_KEY')
        
        self.embeddings = OpenAIEmbeddings(
            openai_api_key=openai_api_key,
            model="text-embedding-3-small"
        )
        
        # FAISS index and metadata storage
        self.index = None
        self.documents = []
        self.metadatas = []
        self.ids = []
        
        # Text splitter for chunking large posts
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
        # Try to load existing index
        self._load_index()
    
    def _load_index(self):
        """Load existing FAISS index if available."""
        index_path = os.path.join(self.db_path, "index.faiss")
        meta_path = os.path.join(self.db_path, "metadata.pkl")
        
        if os.path.exists(index_path) and os.path.exists(meta_path):
            try:
                self.index = faiss.read_index(index_path)
                with open(meta_path, 'rb') as f:
                    data = pickle.load(f)
                    self.documents = data['documents']
                    self.metadatas = data['metadatas']
                    self.ids = data['ids']
                print(f"Loaded existing index with {len(self.documents)} documents")
            except Exception as e:
                print(f"Error loading index: {e}")
                self.index = None
    
    def _save_index(self):
        """Save FAISS index and metadata."""
        if self.index is None:
            return
        
        index_path = os.path.join(self.db_path, "index.faiss")
        meta_path = os.path.join(self.db_path, "metadata.pkl")
        
        faiss.write_index(self.index, index_path)
        with open(meta_path, 'wb') as f:
            pickle.dump({
                'documents': self.documents,
                'metadatas': self.metadatas,
                'ids': self.ids
            }, f)
        print(f"Saved index with {len(self.documents)} documents")
    
    def load_reddit_data(self, json_file: str = 'reddit_discgolf_data.json'):
        """
        Load Reddit data from JSON file and add to knowledge base.
        
        Args:
            json_file: Path to JSON file from reddit_scraper.py
        """
        if not os.path.exists(json_file):
            raise FileNotFoundError(f"Reddit data file not found: {json_file}")
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        posts = data.get('posts', [])
        print(f"Loading {len(posts)} posts into knowledge base...")
        
        # Process each post
        documents = []
        metadatas = []
        ids = []
        
        for post in posts:
            # Create main post document
            post_text = f"Title: {post['title']}\n\n{post['selftext']}"
            
            # Add post metadata
            post_meta = {
                'type': 'post',
                'subreddit': post['subreddit'],
                'score': post['score'],
                'author': post['author'],
                'num_comments': post['num_comments'],
                'post_id': post['id']
            }
            
            # Split long posts into chunks
            if len(post_text) > 1000:
                chunks = self.text_splitter.split_text(post_text)
                for i, chunk in enumerate(chunks):
                    documents.append(chunk)
                    chunk_meta = post_meta.copy()
                    chunk_meta['chunk'] = i
                    metadatas.append(chunk_meta)
                    ids.append(f"{post['id']}_chunk_{i}")
            else:
                documents.append(post_text)
                metadatas.append(post_meta)
                ids.append(f"{post['id']}_post")
            
            # Add top comments as separate documents
            for j, comment in enumerate(post['comments'][:5]):  # Top 5 comments
                if len(comment['body']) > 50:  # Skip very short comments
                    comment_text = f"Comment on: {post['title']}\n\n{comment['body']}"
                    
                    comment_meta = {
                        'type': 'comment',
                        'subreddit': post['subreddit'],
                        'score': comment['score'],
                        'author': comment['author'],
                        'parent_post_id': post['id']
                    }
                    
                    documents.append(comment_text)
                    metadatas.append(comment_meta)
                    ids.append(f"{post['id']}_comment_{j}")
        
        # Generate embeddings in batches
        batch_size = 100
        total_docs = len(documents)
        all_embeddings = []
        
        print(f"Generating embeddings for {total_docs} documents...")
        for i in range(0, total_docs, batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_embeddings = self.embeddings.embed_documents(batch_docs)
            all_embeddings.extend(batch_embeddings)
            print(f"Processed {min(i + batch_size, total_docs)}/{total_docs} documents")
        
        # Convert to numpy array
        embeddings_array = np.array(all_embeddings, dtype='float32')
        
        # Create FAISS index
        dimension = embeddings_array.shape[1]
        self.index = faiss.IndexFlatL2(dimension)  # L2 distance
        self.index.add(embeddings_array)
        
        # Store documents and metadata
        self.documents = documents
        self.metadatas = metadatas
        self.ids = ids
        
        # Save to disk
        self._save_index()
        
        print(f"✅ Successfully loaded {total_docs} documents into knowledge base")
    
    def search(self, query: str, n_results: int = 5, 
               filter_dict: Optional[Dict] = None) -> List[Dict]:
        """
        Search knowledge base with semantic similarity.
        
        Args:
            query: Search query
            n_results: Number of results to return
            filter_dict: Optional metadata filters (e.g., {'subreddit': 'discgolf'})
            
        Returns:
            List of relevant documents with metadata
        """
        if self.index is None or len(self.documents) == 0:
            return []
        
        # Generate query embedding
        query_embedding = self.embeddings.embed_query(query)
        query_array = np.array([query_embedding], dtype='float32')
        
        # Search in FAISS
        distances, indices = self.index.search(query_array, min(n_results * 2, len(self.documents)))
        
        # Format results and apply filters
        formatted_results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # Invalid index
                continue
            
            result = {
                'text': self.documents[idx],
                'metadata': self.metadatas[idx],
                'distance': float(dist)
            }
            
            # Apply filter if provided
            if filter_dict:
                matches = all(result['metadata'].get(k) == v for k, v in filter_dict.items())
                if not matches:
                    continue
            
            formatted_results.append(result)
            
            if len(formatted_results) >= n_results:
                break
        
        return formatted_results
    
    def get_context_for_query(self, query: str, max_results: int = 3) -> str:
        """
        Get formatted context from knowledge base for a query.
        Useful for RAG (Retrieval Augmented Generation).
        
        Args:
            query: User query
            max_results: Maximum number of results to include
            
        Returns:
            Formatted context string
        """
        results = self.search(query, n_results=max_results)
        
        if not results:
            return "No relevant information found in knowledge base."
        
        context_parts = []
        for i, result in enumerate(results, 1):
            meta = result['metadata']
            text = result['text']
            
            # Format based on type
            if meta.get('type') == 'post':
                header = f"[Reddit Post from r/{meta['subreddit']} | Score: {meta['score']}]"
            else:
                header = f"[Comment | Score: {meta['score']}]"
            
            context_parts.append(f"{header}\n{text}\n")
        
        return "\n---\n".join(context_parts)
    
    def get_stats(self) -> Dict:
        """Get knowledge base statistics."""
        count = len(self.documents) if self.documents else 0
        return {
            'total_documents': count,
            'db_path': self.db_path
        }
    
    def clear(self):
        """Clear all data from knowledge base."""
        self.index = None
        self.documents = []
        self.metadatas = []
        self.ids = []
        
        # Remove saved files
        index_path = os.path.join(self.db_path, "index.faiss")
        meta_path = os.path.join(self.db_path, "metadata.pkl")
        
        if os.path.exists(index_path):
            os.remove(index_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        
        print("Knowledge base cleared")


class SimpleTextKnowledgeBase:
    """
    Simple text-based knowledge base without embeddings.
    Faster but less intelligent - uses keyword matching.
    """
    
    def __init__(self, text_file: str = 'discgolf_knowledge.txt'):
        """
        Initialize with text file.
        
        Args:
            text_file: Path to knowledge base text file
        """
        self.text_file = text_file
        self.content = ""
        
        if os.path.exists(text_file):
            with open(text_file, 'r', encoding='utf-8') as f:
                self.content = f.read()
    
    def search(self, query: str, context_window: int = 500) -> List[str]:
        """
        Simple keyword search with context.
        
        Args:
            query: Search query
            context_window: Characters to include around match
            
        Returns:
            List of text snippets containing query
        """
        if not self.content:
            return []
        
        query_lower = query.lower()
        content_lower = self.content.lower()
        
        results = []
        start = 0
        
        while True:
            # Find next occurrence
            pos = content_lower.find(query_lower, start)
            if pos == -1:
                break
            
            # Extract context around match
            snippet_start = max(0, pos - context_window)
            snippet_end = min(len(self.content), pos + len(query) + context_window)
            snippet = self.content[snippet_start:snippet_end]
            
            # Clean up snippet
            if snippet_start > 0:
                snippet = "..." + snippet
            if snippet_end < len(self.content):
                snippet = snippet + "..."
            
            results.append(snippet)
            start = pos + len(query)
            
            # Limit results
            if len(results) >= 5:
                break
        
        return results


def main():
    """
    Example usage of the knowledge base system.
    """
    print("=" * 80)
    print("DISC GOLF KNOWLEDGE BASE SETUP")
    print("=" * 80)
    print()
    
    # Check if Reddit data exists
    if not os.path.exists('reddit_discgolf_data.json'):
        print("⚠️  No Reddit data found!")
        print()
        print("First, run the Reddit scraper to collect data:")
        print("  python reddit_scraper.py")
        print()
        print("Then run this script again to build the knowledge base.")
        return
    
    # Check for OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("⚠️  OPENAI_API_KEY not found in environment variables")
        print()
        print("Set your API key:")
        print("  Windows: $env:OPENAI_API_KEY='your-key-here'")
        print("  Linux/Mac: export OPENAI_API_KEY='your-key-here'")
        return
    
    print("Initializing knowledge base...")
    kb = DiscGolfKnowledgeBase()
    
    # Load Reddit data
    print("\nLoading Reddit data...")
    kb.load_reddit_data('reddit_discgolf_data.json')
    
    # Show stats
    stats = kb.get_stats()
    print(f"\n✅ Knowledge Base Ready!")
    print(f"   Total documents: {stats['total_documents']}")
    print(f"   Database path: {stats['db_path']}")
    
    # Example searches
    print("\n" + "=" * 80)
    print("EXAMPLE SEARCHES")
    print("=" * 80)
    
    example_queries = [
        "best disc for beginners",
        "understable fairway driver",
        "what putter should I buy"
    ]
    
    for query in example_queries:
        print(f"\n🔍 Query: '{query}'")
        print("-" * 80)
        
        results = kb.search(query, n_results=2)
        for i, result in enumerate(results, 1):
            meta = result['metadata']
            text = result['text'][:200] + "..."
            print(f"\nResult {i} (Score: {meta.get('score', 'N/A')} from r/{meta.get('subreddit', 'N/A')}):")
            print(text)
    
    print("\n" + "=" * 80)
    print("Knowledge base is ready for use in your app!")
    print("See the integration example in the comments.")


if __name__ == "__main__":
    main()
