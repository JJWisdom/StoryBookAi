import requests
import sys

print("Checking Forge details...")
print("=" * 60)

# Try to get the full response from the root
try:
    response = requests.get("http://127.0.0.1:7860/", timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response length: {len(response.text)} chars")
    
    # Look for clues in the HTML
    if "gradio" in response.text.lower():
        print("✓ Found Gradio (web UI is running)")
    if "api" in response.text.lower():
        print("✓ Found API references")
        
    # Save the response to a file to examine
    with open("forge_response.html", "w", encoding="utf-8") as f:
        f.write(response.text[:5000])
    print("✓ Saved response to forge_response.html")
    
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)

# Try different API endpoints
endpoints = [
    "/sdapi/v1/sd-models",
    "/api/v1/sd-models",
    "/docs",
    "/docs/api",
    "/api/docs",
    "/v1/sd-models",
    "/api/sd-models"
]

print("Testing various API endpoints:")
for endpoint in endpoints:
    try:
        response = requests.get(f"http://127.0.0.1:7860{endpoint}", timeout=5)
        print(f"{endpoint:30} -> {response.status_code}")
    except:
        print(f"{endpoint:30} -> Failed")