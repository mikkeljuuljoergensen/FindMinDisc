#!/usr/bin/env python3
"""
FindMinDisc Complete Test Runner
=================================
Runs all test suites and generates a comprehensive report.

Usage:
    python run_all_tests.py [--skip-ai]

Options:
    --skip-ai    Skip AI tests even if API key is available
"""

import sys
import os
import subprocess
import time
from datetime import datetime

# ANSI color codes for pretty output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(text):
    """Print a formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}{Colors.ENDC}\n")

def print_section(text):
    """Print a section header"""
    print(f"\n{Colors.OKBLUE}{Colors.BOLD}{text}{Colors.ENDC}")
    print("-" * 70)

def print_success(text):
    """Print success message"""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")

def print_failure(text):
    """Print failure message"""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")

def print_warning(text):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")

def run_test_suite(name, command, timeout=300):
    """
    Run a test suite and return results.
    
    Args:
        name: Test suite name
        command: Command to run
        timeout: Timeout in seconds
    
    Returns:
        dict with 'passed', 'output', and 'duration' keys
    """
    print_section(f"Running: {name}")
    start_time = time.time()
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        duration = time.time() - start_time
        passed = result.returncode == 0
        
        # Print output
        if result.stdout:
            print(result.stdout)
        if result.stderr and not passed:
            print(f"\n{Colors.FAIL}STDERR:{Colors.ENDC}")
            print(result.stderr)
        
        return {
            'passed': passed,
            'output': result.stdout,
            'stderr': result.stderr,
            'duration': duration
        }
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        print_failure(f"Test timed out after {timeout} seconds")
        return {
            'passed': False,
            'output': "",
            'stderr': f"Timeout after {timeout}s",
            'duration': duration
        }
    except Exception as e:
        duration = time.time() - start_time
        print_failure(f"Error running test: {e}")
        return {
            'passed': False,
            'output': "",
            'stderr': str(e),
            'duration': duration
        }

def check_api_key():
    """Check if OpenAI API key is available"""
    api_key = os.environ.get('OPENAI_API_KEY')
    if api_key:
        # Mask the key for display
        masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print_info(f"OpenAI API key found: {masked}")
        return True
    else:
        print_warning("OpenAI API key not found")
        print_info("Set with: export OPENAI_API_KEY='your-key-here'")
        return False

def main():
    """Main test runner"""
    skip_ai = '--skip-ai' in sys.argv
    
    print_header("FindMinDisc Complete Test Suite")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check environment
    print_section("Environment Check")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Working directory: {os.getcwd()}")
    
    # Check for required files
    required_files = [
        'test_app.py',
        'disc_database.json',
        'disc_database_full.json'
    ]
    
    missing_files = [f for f in required_files if not os.path.exists(f)]
    if missing_files:
        print_failure(f"Missing required files: {missing_files}")
        print_info("Make sure you're running from the repository root")
        return 1
    
    print_success("All required files found")
    
    # Check API key for AI tests
    has_api_key = check_api_key()
    
    # Results tracking
    results = {}
    total_duration = 0
    
    # Test Suite 1: Basic Functionality Tests
    print_header("Test Suite 1: Basic Functionality Tests")
    result = run_test_suite(
        "Basic Functionality (test_app.py)",
        f"{sys.executable} test_app.py",
        timeout=60
    )
    results['basic'] = result
    total_duration += result['duration']
    
    if result['passed']:
        print_success(f"Basic tests passed ({result['duration']:.1f}s)")
    else:
        print_failure(f"Basic tests failed ({result['duration']:.1f}s)")
    
    # Test Suite 2 & 3: AI Tests (if API key available and not skipped)
    if has_api_key and not skip_ai:
        # AI Integration Tests
        print_header("Test Suite 2: AI Integration Tests")
        result = run_test_suite(
            "AI Integration (test_handle_free_form.py)",
            f"{sys.executable} test_handle_free_form.py",
            timeout=120
        )
        results['ai_integration'] = result
        total_duration += result['duration']
        
        if result['passed']:
            print_success(f"AI integration tests passed ({result['duration']:.1f}s)")
        else:
            print_failure(f"AI integration tests failed ({result['duration']:.1f}s)")
        
        # Comprehensive AI Tests
        print_header("Test Suite 3: Comprehensive AI Response Tests")
        print_info("This may take 5-10 minutes...")
        result = run_test_suite(
            "Comprehensive AI Tests (test_ai_responses.py)",
            f"{sys.executable} test_ai_responses.py",
            timeout=600
        )
        results['ai_comprehensive'] = result
        total_duration += result['duration']
        
        if result['passed']:
            print_success(f"Comprehensive AI tests passed ({result['duration']:.1f}s)")
        else:
            print_failure(f"Comprehensive AI tests failed ({result['duration']:.1f}s)")
    else:
        if skip_ai:
            print_warning("Skipping AI tests (--skip-ai flag)")
        else:
            print_warning("Skipping AI tests (no API key)")
        print_info("To run AI tests:")
        print_info("  Windows: $env:OPENAI_API_KEY = 'your-key'")
        print_info("  Linux/Mac: export OPENAI_API_KEY='your-key'")
    
    # Final Summary
    print_header("Test Summary")
    
    passed_count = sum(1 for r in results.values() if r['passed'])
    total_count = len(results)
    
    print(f"Total test suites run: {total_count}")
    print(f"Passed: {passed_count}")
    print(f"Failed: {total_count - passed_count}")
    print(f"Total duration: {total_duration:.1f}s ({total_duration/60:.1f}m)")
    
    print("\nDetailed Results:")
    for name, result in results.items():
        status = "✅ PASS" if result['passed'] else "❌ FAIL"
        print(f"  {status} - {name} ({result['duration']:.1f}s)")
    
    # Recommendations
    print_header("Recommendations")
    
    if passed_count == total_count:
        print_success("All tests passed! The chatbot is working correctly.")
        if not has_api_key or skip_ai:
            print_info("Consider running AI tests for full validation")
    else:
        print_failure("Some tests failed. Review the output above for details.")
        
        if 'basic' in results and not results['basic']['passed']:
            print_warning("Basic tests failed - fix these first before running AI tests")
        
        if 'ai_integration' in results and not results['ai_integration']['passed']:
            print_warning("AI integration issues detected")
        
        if 'ai_comprehensive' in results and not results['ai_comprehensive']['passed']:
            print_info("Some AI tests may fail intermittently due to LLM variance")
            print_info("Review specific failures to determine if they're critical")
    
    print("\n" + "="*70)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    # Return exit code
    return 0 if passed_count == total_count else 1

if __name__ == "__main__":
    sys.exit(main())
