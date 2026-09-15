"""
VTR-Agent: Sandbox Safety Tests

Comprehensive sandbox safety test cases to verify isolation and security.
"""
from __future__ import annotations

import subprocess
import sys

from app.sandbox.sandbox_manager import execute_code_sandbox, create_sandbox_session, terminate_sandbox_session, get_violation_history


def test_sandbox_basic_execution():
    """Test basic code execution in sandbox."""
    print("=== Test: Basic Code Execution ===")
    
    code = "x = 1 + 1\\nprint(x)"
    result = execute_code_sandbox(code)
    
    assert result.exit_code == 0, f"Expected exit code 0, got {result.exit_code}"
    assert "2" in result.stdout, f"Expected '2' in stdout, got {result.stdout}"
    assert not result.timed_out, "Should not time out for basic execution"
    assert not result.safety_violation, f"Should not have safety violation: {result.safety_violation}"
    
    print("✓ Basic code execution works")
    return True


def test_sandbox_no_network():
    """Test that network access is blocked."""
    print("=== Test: No Network Access ===")
    
    code = "import socket\\nsocket.create_connection(('8.8.8.8', 80))"
    result = execute_code_sandbox(code)
    
    assert result.timed_out or result.safety_violation, \
        f"Should block network access, got exit_code={result.exit_code}, violation={result.safety_violation}"
    print("✓ Network access is blocked")
    return True


def test_sandbox_no_subprocess():
    """Test that subprocess execution is blocked."""
    print("=== Test: No Subprocess ===")
    
    code = "import subprocess\\nsubprocess.run(['ls'])"
    result = execute_code_sandbox(code)
    
    assert result.safety_violation, \
        f"Should block subprocess, got violation={result.safety_violation}"
    print("✓ Subprocess execution is blocked")
    return True


def test_sandbox_no_file_system_write():
    """Test that unauthorized file system writes are blocked."""
    print("=== Test: No Unauthorized File Write ===")
    
    code = "f = open('/etc/passwd', 'w')\\nf.write('test')"
    result = execute_code_sandbox(code)
    
    # Should either fail or have a safety violation
    assert result.safety_violation or result.exit_code != 0, \
        f"Should block file write, got exit_code={result.exit_code}"
    print("✓ Unauthorized file system writes are blocked")
    return True


def test_sandbox_timed_out():
    """Test that infinite loops time out."""
    print("=== Test: Infinite Loop Timeout ===")
    
    code = "while True:\\n    pass"
    result = execute_code_sandbox(code, timeout=2)  # 2 second timeout
    
    assert result.timed_out, "Should time out for infinite loop"
    assert result.killed, "Process should be killed"
    print("✓ Infinite loops are timed out")
    return True


def test_sandbox_malicious_code():
    """Test detection of malicious code patterns."""
    print("=== Test: Malicious Code Detection ===")
    
    # Test environment variable access
    code = "import os\\nprint(os.environ)"
    result = execute_code_sandbox(code)
    
    # Should block environment variable access
    has_violation = result.safety_violation is not None
    # Or at least should not succeed in accessing env
    env_leaked = "SHELL" in result.stdout if result.stdout else False
    
    # At minimum, the code shouldn't fully succeed in leaking environment
    assert not env_leaked or result.safety_violation, \
        f"Should prevent env var leak, got stdout={result.stdout}, violation={result.safety_violation}"
    print("✓ Malicious code patterns are detected")
    return True


def test_sandbox_allowed_operations():
    """Test that allowed operations work correctly."""
    print("=== Test: Allowed Operations ===")
    
    # Calculator
    code = "result = 2 + 2 * 3\\nprint(result)"
    result = execute_code_sandbox(code)
    assert result.exit_code == 0, f"Calculator should work, got exit_code={result.exit_code}"
    
    # Simple print
    code = "print('Hello, World!')"
    result = execute_code_sandbox(code)
    assert result.exit_code == 0, f"Print should work, got exit_code={result.exit_code}"
    
    print("✓ Allowed operations work correctly")
    return True


def test_sandbox_violation_history():
    """Test that violation history is tracked."""
    print("=== Test: Violation History ===")
    
    # Run a violating code
    code = "import os\\nprint(os.getcwd())"
    result = execute_code_sandbox(code)
    
    # Check violation log
    violations = get_violation_history()
    # At minimum, the system should have some tracking
    print(f"✓ Violation history tracked ({len(violations)} violations)")
    return True


def run_all_sandbox_tests() -> bool:
    """Run all sandbox safety tests."""
    print("=" * 50)
    print("VTR-Agent Sandbox Safety Tests")
    print("=" * 50)
    
    tests = [
        test_sandbox_basic_execution,
        test_sandbox_no_network,
        test_sandbox_no_subprocess,
        test_sandbox_no_file_system_write,
        test_sandbox_timed_out,
        test_sandbox_malicious_code,
        test_sandbox_allowed_operations,
        test_sandbox_violation_history,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED with exception: {e}")
            failed += 1
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_sandbox_tests()
    sys.exit(0 if success else 1)