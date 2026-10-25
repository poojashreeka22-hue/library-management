"""Test runner script that executes pytest and displays clear PASS output."""
import sys
import pytest

if __name__ == "__main__":
    print("=" * 65)
    print(" Executing FastAPI Test Suite with Pytest")
    print("=" * 65)
    
    exit_code = pytest.main(["-v", "tests"])
    
    print("=" * 65)
    if exit_code == 0:
        print(" RESULT: [PASS] All test cases passed successfully!")
    else:
        print(f" RESULT: [FAIL] Tests exited with code {exit_code}")
    print("=" * 65)
    
    sys.exit(exit_code)
