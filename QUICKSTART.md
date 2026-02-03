# FindMinDisc AI Chatbot - Quick Start

## 🎯 What is FindMinDisc?

FindMinDisc is an AI-powered chatbot that helps disc golf players find the perfect discs for their game. It provides personalized recommendations based on skill level, throwing style, and specific needs.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set API Key (Required for AI features)
```bash
# Windows PowerShell
$env:OPENAI_API_KEY = 'your-api-key-here'

# Linux/Mac
export OPENAI_API_KEY='your-api-key-here'
```

### 3. Run the App
```bash
streamlit run app.py
```

Then open http://localhost:8501 in your browser!

## ✅ Testing the Chatbot

### Quick Test (5 seconds)
```bash
python test_app.py
```

### Complete Test Suite
```bash
python run_all_tests.py
```

See [TESTING.md](TESTING.md) for detailed testing documentation.

## 📊 Test Results

**Latest Test Run**: 2026-02-03  
**Status**: ✅ All 54 core tests passed

See [TEST_REPORT.md](TEST_REPORT.md) for the complete test report.

## 🎮 Features

- **Natural Language Queries**: Ask questions in Danish or English
- **Personalized Recommendations**: Get discs matched to your skill level
- **Flight Charts**: Visual comparison of disc flight paths
- **Speed Range Filtering**: Find discs by specific speed ranges (e.g., "7-9 speed")
- **Disc Type Detection**: Automatically identifies putters, midrange, fairway, and distance drivers
- **Knowledge Base**: Integrated with 500+ Reddit disc golf discussions
- **Retailer Links**: Direct links to purchase recommended discs

## 📝 Example Queries

Try asking:
- "jeg søger en understabil 7-9 speed disc" (I'm looking for an understable 7-9 speed disc)
- "anbefal en god putter til begyndere" (recommend a good putter for beginners)
- "fortæl mig mere om Destroyer" (tell me more about Destroyer)
- "sammenlign Volt og Escape" (compare Volt and Escape)

## 📚 Documentation

- [TESTING.md](TESTING.md) - Complete testing guide
- [TEST_REPORT.md](TEST_REPORT.md) - Latest test results
- [INTEGRATION_GUIDE.py](INTEGRATION_GUIDE.py) - Integration documentation

## 🗄️ Database

- **1,471 discs** with complete flight numbers
- **Flight path data** for all discs (slow, normal, fast arm speeds)
- **500 Reddit posts** for knowledge base
- **Manufacturer information** for all discs

## 🔧 Requirements

- Python 3.8+
- OpenAI API key (for AI features)
- See [requirements.txt](requirements.txt) for full dependency list

## 🤝 Contributing

Found a bug? Want to add a feature? Contributions are welcome!

1. Run the test suite to ensure everything works
2. Make your changes
3. Run the tests again to verify
4. Submit a pull request

## 📄 License

See repository for license information.

---

**Happy disc golfing! 🥏**
