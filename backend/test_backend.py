#!/usr/bin/env python3
"""Test script to verify backend modules work correctly"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from database import Database
    print("✅ Database module imported successfully")
    
    from models import QueryOutput, State, QueryResult
    print("✅ Models module imported successfully")
    
    from sql_assistant import SQLAssistApp
    print("✅ SQL Assistant module imported successfully")
    
    from utils import display_results, chinook_test_questions
    print("✅ Utils module imported successfully")
    
    print("\n🎉 All backend modules imported successfully!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)
