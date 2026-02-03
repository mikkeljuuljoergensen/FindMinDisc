# FindMinDisc AI Chatbot - Testing Guide

This guide explains how to test the FindMinDisc AI chatbot to ensure all functionality works correctly.

## Test Overview

The FindMinDisc chatbot has three levels of testing:

### 1. Basic Functionality Tests (No API Key Required)
- **File**: `test_app.py`
- **Tests**: 54 tests covering core functionality
- **Run Time**: ~5-10 seconds
- **Coverage**:
  - Database loading and validation
  - Flight number correction
  - Speed range filtering
  - Disc type detection
  - Flight path generation
  - Knowledge base integration
  - Retailers integration

### 2. AI Integration Tests (Requires OpenAI API Key)
- **File**: `test_handle_free_form.py`
- **Tests**: 3 integration tests
- **Run Time**: ~30-60 seconds
- **Coverage**:
  - Speed range queries
  - "Tell me more" queries
  - Beginner recommendations

### 3. Comprehensive AI Response Tests (Requires OpenAI API Key)
- **File**: `test_ai_responses.py`
- **Tests**: 20+ AI response tests
- **Run Time**: ~5-10 minutes
- **Coverage**:
  - Speed range enforcement
  - Flight number accuracy
  - Understable/overstable detection
  - Beginner recommendations
  - Wind disc recommendations
  - Manufacturer name correction
  - Danish language responses

## Running the Tests

### Quick Test (Basic Functionality)

```bash
python test_app.py
```

This runs all basic tests without requiring an OpenAI API key.

**Expected Output**:
```
✅ All tests passed!
Total: 54 passed, 0 failed, 0 warnings
```

### Full AI Integration Tests

To run the AI tests, you need an OpenAI API key:

**Windows (PowerShell)**:
```powershell
$env:OPENAI_API_KEY = 'your-api-key-here'
python test_handle_free_form.py
python test_ai_responses.py
```

**Linux/Mac**:
```bash
export OPENAI_API_KEY='your-api-key-here'
python test_handle_free_form.py
python test_ai_responses.py
```

### Run All Tests (Convenience Script)

Use the provided test runner:

```bash
python run_all_tests.py
```

This will:
1. Run basic tests first
2. Check if OpenAI API key is available
3. Run AI tests if key is present
4. Generate a comprehensive test report

## Test Results Interpretation

### ✅ PASS
The test passed successfully. The chatbot behaves as expected.

### ❌ FAIL
The test failed. This indicates a bug or incorrect behavior that needs fixing.

### ⚠️ WARN
A warning indicates optional features that are missing or sub-optimal behavior that doesn't break core functionality.

## What Each Test Suite Validates

### test_app.py - Basic Functionality
1. **Database Loading**: Ensures disc databases load correctly
2. **Flight Numbers**: Validates key discs have correct speed/glide/turn/fade
3. **Flight Number Correction**: Tests AI response post-processing
4. **Speed Filtering**: Ensures discs outside requested speed range are filtered
5. **Pattern Detection**: Tests detection of disc types, speed ranges, and "tell me more" patterns
6. **Flight Path Data**: Validates flight simulation data exists
7. **Knowledge Base**: Checks Reddit data and FAISS index
8. **Integrations**: Tests retailers and flight chart modules
9. **Syntax**: Ensures app.py has no syntax errors

### test_handle_free_form.py - AI Integration
1. **Speed Range Query**: Tests "7-9 speed disc" queries
2. **Tell Me More**: Tests detailed disc information requests
3. **Beginner Recommendations**: Tests putter recommendations for beginners

### test_ai_responses.py - Comprehensive AI Tests
1. **Speed Range 7-9**: Fairway drivers only
2. **Speed Range 10-14**: Distance drivers only
3. **Tell Me More Database**: Correct flight numbers from database
4. **Roadrunner Flight**: Specific disc accuracy (9/5/-4/1)
5. **Volt Flight**: Specific disc accuracy (8/5/-0.5/2)
6. **Putter Speed**: Only 1-3 speed discs for putters
7. **Midrange Speed**: Only 4-6 speed discs for midrange
8. **Understable Detection**: Negative turn values
9. **Overstable Detection**: Positive turn or high fade
10. **Flight Number Correction**: AI hallucination fixes
11. **Beginner Recommendations**: Understable, low-speed discs
12. **Wind Disc Recommendations**: Overstable discs for wind
13. **Hyzer Flip Recommendations**: Understable discs
14. **Approach Discs**: Short-range putters/midrange
15. **Multiple Disc Requests**: 2-3 recommendations
16. **Specific Manufacturer**: Brand-specific queries
17. **Straight Flying**: Neutral flight numbers
18. **Max Distance**: High-speed drivers
19. **Speed Filter Testing**: Post-processing validation
20. **Danish Language**: Response in Danish

## Common Issues and Solutions

### Issue: "OPENAI_API_KEY not set"
**Solution**: Set your OpenAI API key as an environment variable before running AI tests.

### Issue: "No module named 'streamlit'"
**Solution**: Install dependencies: `pip install -r requirements.txt`

### Issue: "FileNotFoundError: disc_database.json"
**Solution**: Ensure you're running tests from the repository root directory.

### Issue: Tests timeout or run very slowly
**Solution**: AI tests make real API calls and can take several minutes. This is expected behavior.

### Issue: Intermittent AI test failures
**Solution**: AI responses can vary slightly between runs. A few intermittent failures in AI tests are expected due to the stochastic nature of LLMs. The post-processing logic (flight number correction, speed filtering) should catch most issues.

## Test Coverage Summary

| Component | Test Coverage | Notes |
|-----------|---------------|-------|
| Database Loading | ✅ Comprehensive | All disc data validated |
| Flight Number Accuracy | ✅ Comprehensive | Post-processing ensures correctness |
| Speed Range Filtering | ✅ Comprehensive | Both detection and enforcement |
| Disc Type Detection | ✅ Comprehensive | Putter/Midrange/Fairway/Distance |
| AI Recommendations | ✅ Extensive | 20+ test scenarios |
| Flight Path Generation | ✅ Good | Basic validation |
| Knowledge Base | ✅ Good | Reddit data integration |
| Retailers | ✅ Basic | Link generation tested |
| UI/Streamlit | ⚠️ Manual | Requires manual testing |

## Manual Testing Checklist

While automated tests cover most functionality, some features require manual testing:

- [ ] Run the Streamlit app: `streamlit run app.py`
- [ ] Test flight chart visualization
- [ ] Test retailer links open correctly
- [ ] Test "Tell me more" conversation flow
- [ ] Test flight path animations
- [ ] Test responsive design on mobile
- [ ] Test all language (Danish) rendering correctly
- [ ] Test error handling with invalid inputs

## Continuous Testing

To ensure ongoing quality:

1. Run `python test_app.py` before every commit
2. Run full AI tests before major releases
3. Add new test cases when bugs are discovered
4. Update expected values when database is updated

## Test Maintenance

When adding new discs or features:

1. Update `disc_database.json` with accurate flight numbers
2. Add test cases for new disc types or features
3. Verify AI responses include new discs appropriately
4. Update this documentation with new test procedures

## Getting Help

If tests fail unexpectedly:
1. Check the detailed error messages
2. Verify your environment setup (Python version, dependencies)
3. Ensure databases are up-to-date
4. Review recent code changes
5. Check OpenAI API status if AI tests fail

---

**Last Updated**: 2026-02-03
**Test Suite Version**: 1.0
