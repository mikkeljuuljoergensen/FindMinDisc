"""
Agent Training Example
======================
This script demonstrates how to use another AI agent (or human reviewer)
to analyze feedback and suggest improvements to the chatbot.

Usage:
    python agent_training_example.py
"""

from feedback_system import FeedbackSystem
import json


def analyze_feedback_for_training():
    """
    Example of how to prepare feedback for another agent to analyze.
    """
    print("=" * 80)
    print("AGENT TRAINING EXAMPLE")
    print("=" * 80)
    print()
    
    # Initialize feedback system
    fs = FeedbackSystem()
    
    # Check if we have feedback
    stats = fs.get_feedback_stats()
    if stats["total_count"] == 0:
        print("⚠️  No feedback data available yet.")
        print()
        print("To use this feature:")
        print("1. Run the chatbot: streamlit run app.py")
        print("2. Have some conversations and rate the responses")
        print("3. Run this script again")
        return
    
    print(f"📊 Found {stats['total_count']} feedback entries")
    print(f"   👍 Positive: {stats['positive_count']}")
    print(f"   👎 Negative: {stats['negative_count']}")
    print(f"   💬 With text: {stats['with_text']}")
    print()
    
    # Export for training
    print("📤 Exporting feedback for training...")
    fs.export_for_training("training_data.json")
    print("   ✅ Exported to training_data.json")
    print()
    
    # Show examples that need improvement
    print("=" * 80)
    print("NEGATIVE FEEDBACK (Needs Improvement)")
    print("=" * 80)
    print()
    
    negative = fs.get_negative_feedback()
    if len(negative) > 0:
        for i, entry in enumerate(negative[:5], 1):
            print(f"Example {i}:")
            print(f"  Question: {entry['question']}")
            print(f"  Response: {entry['response'][:150]}...")
            print(f"  Rating: {entry.get('rating', 'N/A')}")
            if entry.get('text_feedback'):
                print(f"  Feedback: {entry['text_feedback']}")
            print()
    else:
        print("✅ No negative feedback - great job!")
    
    print()
    print("=" * 80)
    print("POSITIVE FEEDBACK (Working Well)")
    print("=" * 80)
    print()
    
    positive = fs.get_positive_feedback()
    if len(positive) > 0:
        for i, entry in enumerate(positive[:3], 1):
            print(f"Example {i}:")
            print(f"  Question: {entry['question']}")
            print(f"  Response: {entry['response'][:150]}...")
            print(f"  Rating: {entry.get('rating', 'N/A')}")
            if entry.get('text_feedback'):
                print(f"  Feedback: {entry['text_feedback']}")
            print()
    else:
        print("⚠️  No positive feedback yet")
    
    print()
    print("=" * 80)
    print("INSTRUCTIONS FOR TRAINING AGENT")
    print("=" * 80)
    print()
    print("You can now use another AI agent to improve the chatbot:")
    print()
    print("1. Share the training_data.json file with the agent")
    print("2. Ask the agent to:")
    print("   - Analyze patterns in negative feedback")
    print("   - Suggest improvements to responses")
    print("   - Identify edge cases not handled well")
    print("   - Recommend changes to system prompts")
    print()
    print("3. Example prompt for the agent:")
    print("   \"Analyze this chatbot feedback data and suggest 3-5 specific")
    print("   improvements to make the chatbot more helpful. Focus on the")
    print("   negative feedback and identify patterns.\"")
    print()
    print("4. Implement suggested improvements in app.py")
    print("5. Test and collect more feedback")
    print("6. Repeat!")
    print()
    print("=" * 80)


def show_learning_examples():
    """
    Show high-quality examples for training.
    """
    print("\n" + "=" * 80)
    print("TOP LEARNING EXAMPLES")
    print("=" * 80)
    print()
    
    fs = FeedbackSystem()
    examples = fs.get_learning_examples(limit=5)
    
    if len(examples) == 0:
        print("No learning examples available yet.")
        return
    
    for i, entry in enumerate(examples, 1):
        print(f"Example {i}:")
        print(f"  Question: {entry['question']}")
        print(f"  Response: {entry['response'][:200]}...")
        print(f"  Rating: {entry.get('rating', 'N/A')}")
        
        if entry.get('text_feedback'):
            print(f"  Feedback: {entry['text_feedback']}")
        
        if entry.get('disc_names'):
            print(f"  Discs: {', '.join(entry['disc_names'])}")
        
        print()
    
    print("These examples can be used to:")
    print("- Fine-tune language models")
    print("- Add to RAG knowledge base")
    print("- Create test cases")
    print("- Benchmark response quality")


def generate_training_prompt():
    """
    Generate a prompt for another agent to analyze feedback.
    """
    fs = FeedbackSystem()
    
    negative = fs.get_negative_feedback()
    positive = fs.get_positive_feedback()
    
    if len(negative) == 0 and len(positive) == 0:
        print("\nNo feedback available to generate prompt.")
        return
    
    print("\n" + "=" * 80)
    print("GENERATED TRAINING PROMPT")
    print("=" * 80)
    print()
    print("Copy this prompt and share it with another AI agent along with training_data.json:")
    print()
    print("-" * 80)
    print()
    
    prompt = f"""I need help improving a disc golf recommendation chatbot. I've collected user feedback and want you to analyze it and suggest improvements.

The chatbot helps users find the right disc golf discs based on their skill level, throwing distance, and preferences.

Feedback Summary:
- Total feedback: {fs.get_feedback_stats()['total_count']}
- Positive (👍): {fs.get_feedback_stats()['positive_count']}
- Negative (👎): {fs.get_feedback_stats()['negative_count']}
- With detailed comments: {fs.get_feedback_stats()['with_text']}

I've attached training_data.json with the full feedback data.

Please analyze the feedback and provide:
1. Top 3 patterns in negative feedback
2. What the chatbot is doing well (based on positive feedback)
3. 5 specific, actionable improvements I can implement
4. Suggestions for system prompt changes
5. Edge cases the chatbot should handle better

Focus on making the chatbot more accurate, helpful, and user-friendly."""

    print(prompt)
    print()
    print("-" * 80)
    print()
    print("After getting suggestions from the agent:")
    print("1. Review the suggestions carefully")
    print("2. Implement changes in app.py")
    print("3. Test the changes")
    print("4. Collect more feedback")
    print("5. Iterate!")


def main():
    analyze_feedback_for_training()
    show_learning_examples()
    generate_training_prompt()
    
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print()
    print("✓ Review the feedback examples above")
    print("✓ Use training_data.json to train another agent")
    print("✓ Implement suggested improvements")
    print("✓ Test and iterate!")
    print()
    print("Happy training! 🎉")
    print()


if __name__ == "__main__":
    main()
