"""
CareGuard AI - Official Warehouse Test Suite Runner
---------------------------------------------------
Executes all 50 automated tests across all 6 core warehouse behaviour,
localization, kicking, pause, and multi-upload test modules.
"""

import inspect
import sys
import unittest
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def run_test_module(mod_name: str) -> bool:
    mod = __import__(mod_name, fromlist=['*'])
    test_funcs = [
        (name, obj) for name, obj in inspect.getmembers(mod)
        if (name.startswith('test_') and inspect.isfunction(obj))
    ]
    test_classes = [
        (name, obj) for name, obj in inspect.getmembers(mod)
        if (inspect.isclass(obj) and issubclass(obj, unittest.TestCase))
    ]
    
    total = 0
    passed = 0
    failed = 0
    
    print(f"\n========================================")
    print(f"RUNNING: {mod_name}")
    print(f"========================================")
    
    # Run standalone test functions
    for name, func in test_funcs:
        total += 1
        try:
            func()
            passed += 1
            print(f"  [PASS] {name}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {name}: {e}")
            
    # Run unittest.TestCase classes
    for name, cls in test_classes:
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(cls)
        runner = unittest.TextTestRunner(verbosity=2)
        res = runner.run(suite)
        total += res.testsRun
        passed += (res.testsRun - len(res.failures) - len(res.errors))
        failed += (len(res.failures) + len(res.errors))
        
    print(f"SUMMARY: {passed}/{total} PASSED ({failed} failed)")
    return failed == 0

if __name__ == '__main__':
    modules = [
        'tests.test_action_sequencing_and_semantic_arbitration',
        'tests.test_product_validation_and_background_rejection',
        'tests.test_product_kicking_and_carrying',
        'tests.test_product_localization_persistence',
        'tests.test_product_localization_and_kick',
        'tests.test_all_10_warehouse_behaviours',
        'tests.test_event_semantic_gating_and_pause',
        'tests.test_priority_corrections',
    ]
    
    all_ok = True
    for m in modules:
        try:
            ok = run_test_module(m)
            if not ok:
                all_ok = False
        except Exception as e:
            print(f"Error loading {m}: {e}")
            all_ok = False
            
    print(f"\n========================================")
    print(f"FINAL RESULT: {'ALL TESTS PASSED (100%)' if all_ok else 'SOME TESTS FAILED'}")
    print(f"========================================\n")
    sys.exit(0 if all_ok else 1)
