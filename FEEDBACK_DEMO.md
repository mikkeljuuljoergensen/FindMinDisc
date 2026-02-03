# Chatbot Training Feature - Quick Demo

## How It Works

### 1. User Rates a Response
After the chatbot provides an answer, feedback buttons appear:
- 👍 **Thumbs Up**: Mark the response as helpful (rating: 5/5)
- 👎 **Thumbs Down**: Mark the response as unhelpful (rating: 1/5)
- 💬 **Comment**: Add detailed text feedback

### 2. View Feedback Statistics
In the sidebar, expand "📊 Feedback Statistik" to see:
- Total number of feedback entries
- Positive vs negative counts
- Average rating
- Number of entries with text comments

### 3. Train the Chatbot
Developers can:
```python
from feedback_system import FeedbackSystem

fs = FeedbackSystem()

# Get all feedback
feedback = fs.get_all_feedback()

# Export for training
fs.export_for_training("training_data.json")

# Get high-quality examples
examples = fs.get_learning_examples(limit=20)
```

### 4. Use Another Agent to Analyze
```bash
# Export feedback
python agent_training_example.py

# This generates training_data.json which you can share
# with another AI agent to analyze and suggest improvements
```

## Example Workflow

1. **User asks**: "What disc should I get for windy conditions?"
2. **Bot responds**: With disc recommendations
3. **User clicks** 👍 or 👎
4. **Optionally adds** text feedback: "Great suggestions but could you explain why?"
5. **Developer reviews** feedback weekly
6. **Developer exports** data: `fs.export_for_training()`
7. **Developer or AI agent** analyzes patterns
8. **System prompts improved** based on feedback
9. **Bot gets better!** 🎉

## Privacy & Storage

- Feedback stored in `chatbot_feedback.json` (git-ignored)
- No personal information collected
- Only Q&A pairs and ratings
- Can be exported as training data
- Review and delete data as needed

See [FEEDBACK_GUIDE.md](FEEDBACK_GUIDE.md) for complete documentation.
