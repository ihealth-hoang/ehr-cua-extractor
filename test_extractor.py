#!/usr/bin/env python3
"""
Test script for EHR CUA Extractor

Simple test to verify the extractor is working correctly.
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all required imports work"""
    print("🧪 Testing imports...")
    
    try:
        from ehr_cua_extractor import EHRExtractor
        print("✅ EHRExtractor import successful")
    except ImportError as e:
        print(f"❌ Failed to import EHRExtractor: {e}")
        return False
    
    # Test OpenAI CUA components (now local)
    try:
        from agent import Agent
        from computers.default.local_playwright import LocalPlaywrightBrowser
        print("✅ OpenAI CUA components import successful")
    except ImportError as e:
        print(f"❌ Failed to import CUA components: {e}")
        print("💡 Make sure the agent/ and computers/ folders are present")
        return False
        
    return True

def test_extractor_creation():
    """Test creating an EHRExtractor instance"""
    print("\n🧪 Testing EHRExtractor creation...")
    
    try:
        from ehr_cua_extractor import EHRExtractor
        
        extractor = EHRExtractor(
            computer_type="local-playwright",
            debug=True
        )
        print("✅ EHRExtractor instance created successfully")
        print(f"   Computer type: {extractor.computer_type}")
        print(f"   Debug mode: {extractor.debug}")
        print(f"   Tools defined: {len(extractor.ehr_tools)}")
        
        return True
    except Exception as e:
        print(f"❌ Failed to create EHRExtractor: {e}")
        return False

def test_environment():
    """Test environment configuration"""
    print("\n🧪 Testing environment...")
    
    # Check for API key
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        print(f"✅ OPENAI_API_KEY found (length: {len(api_key)})")
    else:
        print("⚠️  OPENAI_API_KEY not set")
    
    # Check for output directory
    output_dir = Path("./ehr_extractions")
    if output_dir.exists():
        print("✅ Output directory exists")
    else:
        print("📁 Creating output directory...")
        output_dir.mkdir(exist_ok=True)
        print("✅ Output directory created")
    
    return True

def main():
    """Run all tests"""
    print("🧪 EHR CUA Extractor Test Suite")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_extractor_creation,
        test_environment
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
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 40)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All tests passed! EHR CUA Extractor is ready to use.")
        print("\n💡 Next steps:")
        print("   1. Set OPENAI_API_KEY in .env file")
        print("   2. Run: python ehr_cua_extractor.py --patient-id test123 --debug")
    else:
        print("❌ Some tests failed. Please resolve issues before using.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
