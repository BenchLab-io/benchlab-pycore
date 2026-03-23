#!/usr/bin/env python3
"""
Simple syntax validation script for benchlab-pycore
This script checks if all modules can be imported without syntax errors.
"""

import sys
import ast

def check_syntax(file_path):
    """Check if a Python file has valid syntax."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return True, None
    except SyntaxError as e:
        return False, f"Syntax error in {file_path}: {e}"
    except Exception as e:
        return False, f"Error reading {file_path}: {e}"

def main():
    """Check syntax of all Python files in the project."""
    files_to_check = [
        'benchlab/__init__.py',
        'benchlab/version.py',
        'benchlab/core/__init__.py',
        'benchlab/core/serial_io.py',
        'benchlab/core/sensor_translation.py',
        'benchlab/core/structures.py',
        'benchlab/core/utils.py',
        'tests/test_core.py'
    ]
    
    all_valid = True
    
    for file_path in files_to_check:
        valid, error = check_syntax(file_path)
        if valid:
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path}: {error}")
            all_valid = False
    
    if all_valid:
        print("\nAll files have valid Python syntax!")
        return 0
    else:
        print("\nSome files have syntax errors!")
        return 1

if __name__ == "__main__":
    sys.exit(main())