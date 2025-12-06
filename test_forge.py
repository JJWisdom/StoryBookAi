"""
test_forge.py - Standalone Forge testing script
Run this to check if Forge is working BEFORE running the GUI
"""

import requests
import time
import sys
import os
from pathlib import Path
import json

def check_forge_alive(port=7860, timeout=5):
    """Check if Forge is already running and responding"""
    print(f"Checking Forge on port {port}...")
    try:
        response = requests.get(f"http://127.0.0.1:{port}/sdapi/v1/sd-models", timeout=timeout)
        if response.status_code == 200:
            models = response.json()
            print(f"✓ Forge is running! Found {len(models)} model(s)")
            for model in models[:3]:  # Show first 3 models
                print(f"  - {model.get('model_name', 'Unknown')}")
            if len(models) > 3:
                print(f"  ... and {len(models)-3} more")
            return True
        else:
            print(f"✗ Forge responded with status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("✗ Forge is not running (connection refused)")
        return False
    except Exception as e:
        print(f"✗ Error checking Forge: {e}")
        return False

def test_generation(port=7860):
    """Test image generation with a simple prompt"""
    print("\nTesting image generation...")
    
    prompt = "a cute cartoon cat, simple drawing, white background"
    
    payload = {
        "prompt": prompt,
        "steps": 20,
        "width": 512,
        "height": 512,
        "cfg_scale": 7,
        "sampler_name": "Euler a",
        "negative_prompt": "blurry, bad quality, deformed",
        "seed": -1
    }
    
    print(f"Prompt: {prompt}")
    print("Sending to Forge...")
    
    try:
        start_time = time.time()
        response = requests.post(
            f"http://127.0.0.1:{port}/sdapi/v1/txt2img",
            json=payload,
            timeout=120  # 2 minutes timeout
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            if "images" in data and data["images"]:
                print(f"✓ Generation successful! ({elapsed:.1f} seconds)")
                
                # Save the test image
                import base64
                from datetime import datetime
                
                image_b64 = data["images"][0]
                image_bin = base64.b64decode(image_b64)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"test_forge_{timestamp}.png"
                with open(filename, "wb") as f:
                    f.write(image_bin)
                
                print(f"✓ Test image saved: {filename}")
                
                # Show generation info
                if "info" in data:
                    info = json.loads(data["info"])
                    print(f"Seed: {info.get('seed', 'N/A')}")
                    print(f"Steps: {info.get('steps', 'N/A')}")
                
                return True
            else:
                print("✗ No images in response")
                print(f"Response: {response.text[:200]}...")
                return False
        else:
            print(f"✗ Forge returned status {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.Timeout:
        print("✗ Generation timeout (2 minutes)")
        return False
    except Exception as e:
        print(f"✗ Generation error: {e}")
        return False

def check_config():
    """Check if config file exists and is valid"""
    print("\nChecking configuration...")
    config_path = Path("storybook_config.json")
    
    if not config_path.exists():
        print("✗ storybook_config.json not found")
        return False
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        forge_path = config.get("forge", {}).get("path", "")
        if forge_path and Path(forge_path).exists():
            print(f"✓ Config found: Forge path = {forge_path}")
            return True
        else:
            print(f"✗ Forge path in config doesn't exist: {forge_path}")
            return False
    except Exception as e:
        print(f"✗ Error reading config: {e}")
        return False

def manual_forge_start():
    """Guide user to start Forge manually if needed"""
    print("\n" + "="*60)
    print("MANUAL FORGE STARTUP INSTRUCTIONS")
    print("="*60)
    
    # Try to get path from config
    try:
        with open("storybook_config.json", 'r') as f:
            config = json.load(f)
        forge_path = config.get("forge", {}).get("path", "")
    except:
        forge_path = ""
    
    if forge_path and Path(forge_path).exists():
        print(f"\n1. Open Command Prompt as Administrator")
        print(f"2. Navigate to: {forge_path}")
        print(f"3. Run: run.bat --api --nowebui --port 7860")
    else:
        print("\n1. Find your Forge UI installation folder")
        print("2. Open Command Prompt in that folder")
        print("3. Run: run.bat --api --nowebui --port 7860")
    
    print("\nWait until you see messages like:")
    print("  - 'Model selected: ...'")
    print("  - 'Running on local URL: http://127.0.0.1:7860'")
    print("  - 'Startup time: ...'")
    print("\nThen run this test script again.")
    print("="*60)

def main():
    print("\n" + "="*60)
    print("FORGE UI TEST SCRIPT")
    print("="*60)
    
    # Check config first
    if not check_config():
        print("\nPlease run setup first or create storybook_config.json")
        response = input("Run setup now? (y/n): ").lower()
        if response == 'y':
            try:
                import setup_forge
                setup_forge.main()
            except Exception as e:
                print(f"Setup failed: {e}")
        return
    
    # Check if Forge is already running
    if check_forge_alive():
        # Test generation
        if test_generation():
            print("\n" + "="*60)
            print("SUCCESS! Forge is working correctly.")
            print("You can now run: python storybookgui.py")
            print("="*60)
            return
        else:
            print("\nForge is running but generation failed.")
            print("This might be a model or configuration issue.")
    else:
        print("\nForge is not running.")
        
        # Try to start Forge automatically
        response = input("\nAttempt to start Forge automatically? (y/n): ").lower()
        if response == 'y':
            print("\nStarting Forge...")
            
            try:
                from forge_handler import ForgeHandler
                
                # Get path from config
                with open("storybook_config.json", 'r') as f:
                    config = json.load(f)
                forge_path = config.get("forge", {}).get("path", "")
                
                if not forge_path or not Path(forge_path).exists():
                    print(f"Invalid Forge path: {forge_path}")
                    manual_forge_start()
                    return
                
                forge = ForgeHandler(forge_path, 7860)
                if forge.start_forge():
                    print("✓ Forge started successfully!")
                    time.sleep(2)  # Give it a moment
                    
                    # Test generation
                    if test_generation():
                        print("\n" + "="*60)
                        print("SUCCESS! Forge is now working.")
                        print("="*60)
                    else:
                        print("\nForge started but generation failed.")
                else:
                    print("✗ Failed to start Forge automatically.")
                    manual_forge_start()
                    
            except Exception as e:
                print(f"Error starting Forge: {e}")
                manual_forge_start()
        else:
            manual_forge_start()
    
    print("\nPress Enter to exit...")
    input()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest cancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")