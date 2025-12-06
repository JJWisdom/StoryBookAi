"""
quick_test.py - Minimal Forge test
"""
import requests
import time

print("Quick Forge Test")
print("=" * 40)

# Test 1: Basic connection
try:
    print("Testing connection to Forge...")
    response = requests.get("http://127.0.0.1:7860/", timeout=10)
    print(f"Response: {response.status_code}")
except requests.exceptions.ConnectionError:
    print("✗ Cannot connect to Forge")
    print("\nMake sure Forge is running with:")
    print("  run.bat --api --nowebui --port 7860")
except Exception as e:
    print(f"Error: {e}")

# Test 2: API endpoint
try:
    print("\nTesting API endpoint...")
    response = requests.get("http://127.0.0.1:7860/sdapi/v1/sd-models", timeout=10)
    if response.status_code == 200:
        print(f"✓ API is working! Found {len(response.json())} model(s)")
    else:
        print(f"✗ API returned {response.status_code}")
except Exception as e:
    print(f"✗ API test failed: {e}")

print("\n" + "=" * 40)
input("Press Enter to exit...")