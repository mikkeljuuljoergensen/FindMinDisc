"""
Chatbot Feedback and Training System
====================================
This module provides functionality for collecting and storing user feedback
on chatbot responses, enabling continuous learning and improvement.

Features:
- Rate chatbot responses (thumbs up/down or star ratings)
- Provide text feedback for responses
- Store feedback with context (question, answer, user preferences)
- Retrieve feedback for analysis and training
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional


class FeedbackSystem:
    """
    Manages feedback collection and storage for chatbot responses.
    """
    
    def __init__(self, feedback_file: str = "chatbot_feedback.json"):
        """
        Initialize feedback system.
        
        Args:
            feedback_file: Path to JSON file for storing feedback
        """
        self.feedback_file = feedback_file
        self.feedback_data = self._load_feedback()
    
    def _load_feedback(self) -> Dict:
        """Load existing feedback from file."""
        if os.path.exists(self.feedback_file):
            try:
                with open(self.feedback_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading feedback: {e}")
                return {"feedback": []}
        return {"feedback": []}
    
    def _save_feedback(self):
        """Save feedback to file."""
        try:
            with open(self.feedback_file, 'w', encoding='utf-8') as f:
                json.dump(self.feedback_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving feedback: {e}")
    
    def add_feedback(
        self,
        question: str,
        response: str,
        rating: Optional[int] = None,
        text_feedback: Optional[str] = None,
        user_prefs: Optional[Dict] = None,
        disc_names: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Add feedback for a chatbot response.
        
        Args:
            question: The user's question
            response: The chatbot's response
            rating: Rating (1-5 stars or -1 for thumbs down, 1 for thumbs up)
            text_feedback: Optional text feedback from user
            user_prefs: User preferences/context at time of question
            disc_names: List of disc names recommended in response
            metadata: Additional metadata (e.g., response time, model used)
        
        Returns:
            Feedback ID
        """
        feedback_id = f"fb_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        feedback_entry = {
            "id": feedback_id,
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "response": response,
            "rating": rating,
            "text_feedback": text_feedback,
            "user_prefs": user_prefs or {},
            "disc_names": disc_names or [],
            "metadata": metadata or {}
        }
        
        self.feedback_data["feedback"].append(feedback_entry)
        self._save_feedback()
        
        return feedback_id
    
    def get_all_feedback(self) -> List[Dict]:
        """Get all stored feedback."""
        return self.feedback_data.get("feedback", [])
    
    def get_feedback_by_rating(self, min_rating: int, max_rating: Optional[int] = None) -> List[Dict]:
        """
        Get feedback filtered by rating.
        
        Args:
            min_rating: Minimum rating (inclusive)
            max_rating: Maximum rating (inclusive, None for no upper limit)
        
        Returns:
            List of feedback entries matching criteria
        """
        feedback_list = self.get_all_feedback()
        filtered = []
        
        for entry in feedback_list:
            rating = entry.get("rating")
            if rating is None:
                continue
            
            if max_rating is None:
                if rating >= min_rating:
                    filtered.append(entry)
            else:
                if min_rating <= rating <= max_rating:
                    filtered.append(entry)
        
        return filtered
    
    def get_positive_feedback(self) -> List[Dict]:
        """Get all positive feedback (rating >= 4 or thumbs up)."""
        return self.get_feedback_by_rating(4)
    
    def get_negative_feedback(self) -> List[Dict]:
        """Get all negative feedback (rating <= 2 or thumbs down)."""
        return self.get_feedback_by_rating(-1, 2)
    
    def get_feedback_with_text(self) -> List[Dict]:
        """Get all feedback that includes text comments."""
        return [
            entry for entry in self.get_all_feedback()
            if entry.get("text_feedback") and entry["text_feedback"].strip()
        ]
    
    def get_feedback_stats(self) -> Dict:
        """
        Get statistics about collected feedback.
        
        Returns:
            Dictionary with statistics
        """
        all_feedback = self.get_all_feedback()
        total_count = len(all_feedback)
        
        if total_count == 0:
            return {
                "total_count": 0,
                "with_rating": 0,
                "with_text": 0,
                "positive_count": 0,
                "negative_count": 0,
                "average_rating": None
            }
        
        with_rating = [f for f in all_feedback if f.get("rating") is not None]
        with_text = len(self.get_feedback_with_text())
        positive = len(self.get_positive_feedback())
        negative = len(self.get_negative_feedback())
        
        # Calculate average rating (only for 1-5 scale ratings)
        ratings = [f["rating"] for f in with_rating if f["rating"] >= 1 and f["rating"] <= 5]
        avg_rating = sum(ratings) / len(ratings) if ratings else None
        
        return {
            "total_count": total_count,
            "with_rating": len(with_rating),
            "with_text": with_text,
            "positive_count": positive,
            "negative_count": negative,
            "average_rating": round(avg_rating, 2) if avg_rating else None
        }
    
    def get_learning_examples(self, limit: int = 20) -> List[Dict]:
        """
        Get high-quality feedback examples for training/learning.
        Prioritizes:
        - Feedback with text comments
        - Highly rated responses
        - Recent feedback
        
        Args:
            limit: Maximum number of examples to return
        
        Returns:
            List of feedback entries suitable for training
        """
        all_feedback = self.get_all_feedback()
        
        # Score each feedback entry
        scored_feedback = []
        for entry in all_feedback:
            score = 0
            
            # Has text feedback (highest priority)
            if entry.get("text_feedback") and entry["text_feedback"].strip():
                score += 10
            
            # Has rating
            rating = entry.get("rating")
            if rating is not None:
                # Positive ratings add more value
                if rating >= 4:
                    score += 5
                elif rating <= 2:
                    score += 3  # Negative feedback is also valuable
            
            # Recency (more recent = higher score)
            try:
                timestamp = datetime.fromisoformat(entry["timestamp"])
                days_old = (datetime.now() - timestamp).days
                # Decay score based on age
                if days_old < 7:
                    score += 2
                elif days_old < 30:
                    score += 1
            except:
                pass
            
            scored_feedback.append((score, entry))
        
        # Sort by score (descending) and return top entries
        scored_feedback.sort(key=lambda x: x[0], reverse=True)
        return [entry for score, entry in scored_feedback[:limit]]
    
    def clear_feedback(self):
        """Clear all feedback (use with caution)."""
        self.feedback_data = {"feedback": []}
        self._save_feedback()
    
    def export_for_training(self, output_file: str = "training_data.json"):
        """
        Export feedback in a format suitable for fine-tuning or RAG.
        
        Args:
            output_file: Path to export file
        """
        training_examples = []
        
        for entry in self.get_learning_examples(limit=1000):
            # Only include high-quality examples
            if entry.get("rating", 0) >= 4 or entry.get("text_feedback"):
                example = {
                    "instruction": entry["question"],
                    "response": entry["response"],
                    "rating": entry.get("rating"),
                    "feedback": entry.get("text_feedback", ""),
                    "context": {
                        "disc_names": entry.get("disc_names", []),
                        "user_prefs": entry.get("user_prefs", {})
                    }
                }
                training_examples.append(example)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(training_examples, f, indent=2, ensure_ascii=False)
        
        print(f"Exported {len(training_examples)} training examples to {output_file}")


def main():
    """
    Example usage of the feedback system.
    """
    print("=" * 80)
    print("CHATBOT FEEDBACK SYSTEM - DEMO")
    print("=" * 80)
    print()
    
    # Initialize system
    fs = FeedbackSystem("demo_feedback.json")
    
    # Add some example feedback
    print("Adding example feedback...")
    
    fs.add_feedback(
        question="What's the best disc for beginners?",
        response="For beginners, I recommend the Leopard...",
        rating=5,
        text_feedback="Very helpful! Exactly what I needed.",
        disc_names=["Leopard", "Aviar"]
    )
    
    fs.add_feedback(
        question="Tell me about Destroyers",
        response="The Destroyer is a high-speed driver...",
        rating=4,
        disc_names=["Destroyer"]
    )
    
    fs.add_feedback(
        question="Best putter?",
        response="I recommend checking out the Berg...",
        rating=2,
        text_feedback="I was looking for putters, not approach discs.",
        disc_names=["Berg"]
    )
    
    # Show statistics
    print("\nFeedback Statistics:")
    stats = fs.get_feedback_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    # Show learning examples
    print("\nTop Learning Examples:")
    examples = fs.get_learning_examples(limit=3)
    for i, example in enumerate(examples, 1):
        print(f"\n  Example {i}:")
        print(f"    Q: {example['question']}")
        print(f"    Rating: {example.get('rating', 'N/A')}")
        print(f"    Feedback: {example.get('text_feedback', 'None')}")
    
    print("\n" + "=" * 80)
    print("Demo complete! Check demo_feedback.json")
    
    # Clean up demo file
    if os.path.exists("demo_feedback.json"):
        os.remove("demo_feedback.json")


if __name__ == "__main__":
    main()
