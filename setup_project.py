"""
setup_project.py - Robust project setup script
"""

import os
import sys
import json
import subprocess
import platform
from pathlib import Path
import shutil
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/setup.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def print_header(text: str):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(text)
    print("=" * 60)

def check_python_version() -> bool:
    """Check Python version compatibility"""
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor >= 8:
        print("Python version OK")
        return True
    else:
        print("Python 3.8 or higher required")
        return False

def install_dependencies():
    """Install Python dependencies from requirements.txt"""
    print_header("INSTALLING DEPENDENCIES")
    
    # Upgrade pip first
    print("Upgrading pip...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    except:
        print("Could not upgrade pip, continuing...")
    
    # Require requirements.txt
    req_path = Path("requirements.txt")
    if not req_path.exists():
        print(f"requirements.txt not found at {req_path.absolute()}")
        print("Create it with required packages (e.g., Pillow, requests, psutil, reportlab).")
        return False
    
    # Install from requirements.txt
    print("Installing from requirements.txt...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install from requirements.txt: {e}")
        return False

def setup_forge_ui():
    """Setup Forge UI integration"""
    print_header("SETTING UP FORGE UI")
    
    setup_script = Path("setup_forge.py")
    if setup_script.exists():
        print("Running Forge UI setup...")
        try:
            result = subprocess.run([sys.executable, str(setup_script)], 
                                   capture_output=True, text=True)
            if result.returncode == 0:
                print("Forge UI setup complete")
            else:
                print(f"Forge setup had issues:\n{result.stderr}")
        except Exception as e:
            print(f"Failed to run Forge setup: {e}")
    else:
        print("setup_forge.py not found")
        print("You can manually create storybook_config.json")
        
        # Create minimal config
        config = {
            "forge": {
                "path": "",
                "port": 7860,
                "auto_start": True
            }
        }
        
        config_path = Path("storybook_config.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"Created template config: {config_path}")
        print("WARNING: Forge path is empty. Edit storybook_config.json with a valid path, or run setup_forge.py manually.")
        print("Without this, image generation will fail.")

def create_directories():
    """Create necessary directories"""
    print_header("CREATING DIRECTORIES")
    
    directories = [
        "generated_images",
        "exports",
        "temp",
        "logs"
    ]
    
    for dir_name in directories:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"Created: {dir_name}/")
        else:
            print(f"Already exists: {dir_name}/")

def check_disk_space():
    """Check available disk space and fail if insufficient"""
    try:
        import shutil
        # Use project root instead of cwd for consistency
        project_root = Path(__file__).parent
        usage = shutil.disk_usage(project_root)
        free_gb = usage.free / (1024**3)
        
        print_header("SYSTEM CHECK")
        print(f"Disk space available at {project_root}: {free_gb:.1f} GB")
        
        if free_gb < 5:
            print("Insufficient disk space (5+ GB required for image generation and models)")
            return False
        else:
            print("Sufficient disk space")
            return True
        
    except Exception as e:
        print(f"Could not check disk space: {e}")
        print("Continuing, but ensure at least 5GB free space.")
        return True  # Non-critical failure for MVP

def print_summary():
    """Print setup summary"""
    print_header("SETUP COMPLETE")
    
    print("\nStoryBook AI is ready!")
    print("\nNEXT STEPS:")
    print("1. Configure Forge UI in storybook_config.json")
    print("2. Place Stable Diffusion models in:")
    print("   [Forge UI path]/models/Stable-diffusion/")
    print("\nSTART THE APPLICATION:")
    print("   > python storybookgui.py")
    print("\nQUICK START:")
    print("   - Write a story on the first screen")
    print("   - Click 'Create Storybook' to break into slides")
    print("   - Edit subjects/actions/text for each slide")
    print("   - Click 'Illustrate' to generate images")
    print("   - Click 'Publish' on last slide to export")
    print("\nIMPORTANT NOTES:")
    print("   - First run will start Forge UI (takes 2-5 minutes)")
    print("   - Keep Forge UI running while using the app")
    print("   - Images are saved in 'generated_images/' folder")
    print("   - Exports are saved in 'exports/' folder")

def main():
    """Main setup routine"""
    print_header("STORYBOOK AI SETUP")
    
    # New: Check if running in virtualenv
    if sys.prefix == sys.base_prefix:
        print("This script must be run in a virtual environment (venv).")
        print("Activate your venv first: venv\\Scripts\\activate (Windows) or source venv/bin/activate (Unix).")
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Check Python
    if not check_python_version():
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Install dependencies
    if not install_dependencies():
        print("\nSome dependencies failed to install")
        response = input("Continue anyway? (y/n): ").lower()
        if response != 'y':
            sys.exit(1)
    
    # Setup Forge UI
    setup_forge_ui()
    
    # Create directories
    create_directories()
    
    # Check disk space
    if not check_disk_space():
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Final summary
    print_summary()
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        input("\nPress Enter to exit...")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Setup error: {e}")
        print(f"\nSetup error: {e}")
        input("Press Enter to exit...")
        sys.exit(1)