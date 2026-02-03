"""
Test Suite for Feedback System
================================
Tests the chatbot feedback collection and storage functionality.

Usage:
    python test_feedback_system.py
"""

import json
import os
import sys
from datetime import datetime

# Test counters
PASSED = 0
FAILED = 0
WARNINGS = 0

def log_pass(test_name, details=""):
    global PASSED
    PASSED += 1
    print(f"  ✅ PASS: {test_name}")
    if details:
        print(f"          {details}")

def log_fail(test_name, expected, got):
    global FAILED
    FAILED += 1
    print(f"  ❌ FAIL: {test_name}")
    print(f"          Expected: {expected}")
    print(f"          Got: {got}")

def log_warn(test_name, message):
    global WARNINGS
    WARNINGS += 1
    print(f"  ⚠️  WARN: {test_name}")
    print(f"          {message}")

def section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


# =============================================================================
# TEST 1: Import and Initialization
# =============================================================================
def test_imports_and_init():
    section("TEST 1: Import and Initialization")
    
    try:
        from feedback_system import FeedbackSystem
        log_pass("FeedbackSystem import")
    except Exception as e:
        log_fail("FeedbackSystem import", "Import successful", str(e))
        return None
    
    try:
        fs = FeedbackSystem("test_feedback.json")
        log_pass("FeedbackSystem initialization")
        return fs
    except Exception as e:
        log_fail("FeedbackSystem initialization", "Instance created", str(e))
        return None


# =============================================================================
# TEST 2: Add Feedback
# =============================================================================
def test_add_feedback(fs):
    section("TEST 2: Add Feedback")
    
    if fs is None:
        log_fail("Test setup", "FeedbackSystem instance", "None")
        return
    
    # Test adding feedback with rating
    try:
        feedback_id = fs.add_feedback(
            question="What's the best disc for beginners?",
            response="For beginners, I recommend the Leopard...",
            rating=5,
            disc_names=["Leopard", "Aviar"]
        )
        
        if feedback_id and feedback_id.startswith("fb_"):
            log_pass("Add feedback with rating", f"ID: {feedback_id}")
        else:
            log_fail("Add feedback with rating", "Valid feedback ID", feedback_id)
    except Exception as e:
        log_fail("Add feedback with rating", "Successful addition", str(e))
    
    # Test adding feedback with text
    try:
        feedback_id = fs.add_feedback(
            question="Tell me about Destroyers",
            response="The Destroyer is a high-speed driver...",
            rating=4,
            text_feedback="Great information!",
            disc_names=["Destroyer"]
        )
        
        if feedback_id:
            log_pass("Add feedback with text", f"ID: {feedback_id}")
        else:
            log_fail("Add feedback with text", "Valid feedback ID", feedback_id)
    except Exception as e:
        log_fail("Add feedback with text", "Successful addition", str(e))
    
    # Test adding negative feedback
    try:
        feedback_id = fs.add_feedback(
            question="Best putter?",
            response="I recommend checking out the Berg...",
            rating=2,
            text_feedback="I wanted putters, not approach discs.",
            disc_names=["Berg"]
        )
        
        if feedback_id:
            log_pass("Add negative feedback", f"ID: {feedback_id}")
        else:
            log_fail("Add negative feedback", "Valid feedback ID", feedback_id)
    except Exception as e:
        log_fail("Add negative feedback", "Successful addition", str(e))


# =============================================================================
# TEST 3: Retrieve Feedback
# =============================================================================
def test_retrieve_feedback(fs):
    section("TEST 3: Retrieve Feedback")
    
    if fs is None:
        log_fail("Test setup", "FeedbackSystem instance", "None")
        return
    
    # Test get all feedback
    try:
        all_feedback = fs.get_all_feedback()
        if len(all_feedback) >= 3:
            log_pass("Get all feedback", f"{len(all_feedback)} entries retrieved")
        else:
            log_fail("Get all feedback", "At least 3 entries", f"{len(all_feedback)} entries")
    except Exception as e:
        log_fail("Get all feedback", "List of feedback", str(e))
    
    # Test get positive feedback
    try:
        positive = fs.get_positive_feedback()
        if len(positive) >= 1:
            log_pass("Get positive feedback", f"{len(positive)} positive entries")
        else:
            log_warn("Get positive feedback", f"Expected at least 1, got {len(positive)}")
    except Exception as e:
        log_fail("Get positive feedback", "List of positive feedback", str(e))
    
    # Test get negative feedback
    try:
        negative = fs.get_negative_feedback()
        if len(negative) >= 1:
            log_pass("Get negative feedback", f"{len(negative)} negative entries")
        else:
            log_warn("Get negative feedback", f"Expected at least 1, got {len(negative)}")
    except Exception as e:
        log_fail("Get negative feedback", "List of negative feedback", str(e))
    
    # Test get feedback with text
    try:
        with_text = fs.get_feedback_with_text()
        if len(with_text) >= 2:
            log_pass("Get feedback with text", f"{len(with_text)} entries with text")
        else:
            log_warn("Get feedback with text", f"Expected at least 2, got {len(with_text)}")
    except Exception as e:
        log_fail("Get feedback with text", "List of feedback with text", str(e))


# =============================================================================
# TEST 4: Feedback Statistics
# =============================================================================
def test_feedback_stats(fs):
    section("TEST 4: Feedback Statistics")
    
    if fs is None:
        log_fail("Test setup", "FeedbackSystem instance", "None")
        return
    
    try:
        stats = fs.get_feedback_stats()
        
        # Check required keys
        required_keys = ["total_count", "with_rating", "with_text", "positive_count", "negative_count", "average_rating"]
        for key in required_keys:
            if key in stats:
                log_pass(f"Stats key '{key}'", f"Value: {stats[key]}")
            else:
                log_fail(f"Stats key '{key}'", "Key present", "Key missing")
        
        # Validate counts
        if stats["total_count"] >= 3:
            log_pass("Total count validation", f"{stats['total_count']} entries")
        else:
            log_warn("Total count validation", f"Expected >= 3, got {stats['total_count']}")
        
        if stats["average_rating"] and 1 <= stats["average_rating"] <= 5:
            log_pass("Average rating validation", f"{stats['average_rating']}/5")
        else:
            log_warn("Average rating validation", f"Got {stats['average_rating']}")
            
    except Exception as e:
        log_fail("Get feedback stats", "Stats dictionary", str(e))


# =============================================================================
# TEST 5: Learning Examples
# =============================================================================
def test_learning_examples(fs):
    section("TEST 5: Learning Examples")
    
    if fs is None:
        log_fail("Test setup", "FeedbackSystem instance", "None")
        return
    
    try:
        examples = fs.get_learning_examples(limit=10)
        
        if len(examples) > 0:
            log_pass("Get learning examples", f"{len(examples)} examples retrieved")
        else:
            log_warn("Get learning examples", "No examples retrieved")
        
        # Check that high-quality examples are prioritized
        has_text_feedback = any(e.get("text_feedback") for e in examples)
        if has_text_feedback:
            log_pass("Prioritize text feedback", "Text feedback in top examples")
        else:
            log_warn("Prioritize text feedback", "No text feedback in examples")
            
    except Exception as e:
        log_fail("Get learning examples", "List of examples", str(e))


# =============================================================================
# TEST 6: Export for Training
# =============================================================================
def test_export_training(fs):
    section("TEST 6: Export for Training")
    
    if fs is None:
        log_fail("Test setup", "FeedbackSystem instance", "None")
        return
    
    export_file = "test_training_data.json"
    
    try:
        fs.export_for_training(export_file)
        
        if os.path.exists(export_file):
            log_pass("Export file created", export_file)
            
            # Validate export format
            with open(export_file, 'r', encoding='utf-8') as f:
                training_data = json.load(f)
            
            if isinstance(training_data, list) and len(training_data) > 0:
                log_pass("Export format validation", f"{len(training_data)} examples")
                
                # Check first example structure
                example = training_data[0]
                required_keys = ["instruction", "response", "rating", "feedback", "context"]
                all_keys_present = all(key in example for key in required_keys)
                
                if all_keys_present:
                    log_pass("Export example structure", "All required keys present")
                else:
                    missing = [k for k in required_keys if k not in example]
                    log_fail("Export example structure", "All keys present", f"Missing: {missing}")
            else:
                log_warn("Export format validation", "Empty or invalid training data")
            
            # Clean up
            os.remove(export_file)
        else:
            log_fail("Export file created", "File exists", "File not found")
            
    except Exception as e:
        log_fail("Export for training", "Successful export", str(e))


# =============================================================================
# TEST 7: Persistence (Save/Load)
# =============================================================================
def test_persistence():
    section("TEST 7: Persistence (Save/Load)")
    
    from feedback_system import FeedbackSystem
    
    test_file = "test_persistence.json"
    
    # Create feedback system and add data
    fs1 = FeedbackSystem(test_file)
    feedback_id = fs1.add_feedback(
        question="Test question",
        response="Test response",
        rating=5
    )
    
    count1 = len(fs1.get_all_feedback())
    
    # Create new instance (should load from file)
    fs2 = FeedbackSystem(test_file)
    count2 = len(fs2.get_all_feedback())
    
    if count1 == count2 and count2 > 0:
        log_pass("Persistence test", f"Data persisted: {count2} entries")
    else:
        log_fail("Persistence test", f"{count1} entries", f"{count2} entries")
    
    # Clean up
    if os.path.exists(test_file):
        os.remove(test_file)


# =============================================================================
# RUN ALL TESTS
# =============================================================================
def main():
    print("=" * 60)
    print("  Feedback System Test Suite")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    # Run tests
    fs = test_imports_and_init()
    test_add_feedback(fs)
    test_retrieve_feedback(fs)
    test_feedback_stats(fs)
    test_learning_examples(fs)
    test_export_training(fs)
    test_persistence()
    
    # Clean up test file
    if os.path.exists("test_feedback.json"):
        os.remove("test_feedback.json")
    
    # Print summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)
    print(f"  ✅ PASSED:   {PASSED}")
    print(f"  ❌ FAILED:   {FAILED}")
    print(f"  ⚠️  WARNINGS: {WARNINGS}")
    print("=" * 60)
    
    if FAILED > 0:
        print("  ⚠️  Some tests failed!")
        sys.exit(1)
    else:
        print("  🎉 All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
