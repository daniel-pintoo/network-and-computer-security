#!/usr/bin/env python3
"""
Utility script to fix PostgreSQL sequence after document deletions.
Run this script if you get ID conflicts when creating new documents after deletions.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from database import fix_sequence

if __name__ == "__main__":
    try:
        fix_sequence()
        print("✓ Sequence fixed successfully!")
    except Exception as e:
        print(f"✗ Error fixing sequence: {e}")
        sys.exit(1)

