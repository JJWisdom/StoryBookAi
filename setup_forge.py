"""
setup_forge.py - Simplified and robust Forge UI setup
"""

import os
import sys
import json
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

def setup_forge_interactive():
    """Interactive Forge UI setup with GUI"""
    print("\nForge UI Setup Assistant")
    print("=" * 50)
    
    # Try to create a simple GUI for path selection
    try:
        root = tk.Tk()
        root.withdraw()  # Hide main window
        
        print("\nPlease select your Forge UI installation folder containing webui.py...")
        
        # Open folder dialog
        forge_path = filedialog.askdirectory(
            title="Select Forge UI Installation Folder",
            initialdir=Path.home()
        )
        
        if not forge_path:
            print("Setup cancelled.")
            return None
        
        forge_path = Path(forge_path)
        
        # Validate the selected path
        if not _validate_forge_path(forge_path):
            print(f"\nERROR: Invalid Forge UI installation at: {forge_path}")
            print("\nPlease ensure the folder contains:")
            print("  - webui.py (main script)")
            print("  - A launch script like webui.bat or run.bat")
            print("  - models/ folder")
            print("For portable versions, select the 'webui' subfolder if applicable.")
            
            retry = input("\nTry again? (y/n): ").lower()
            if retry.startswith('y'):
                return setup_forge_interactive()
            return None
        
        print(f"\nSUCCESS: Valid Forge UI found at: {forge_path}")
        
        # Create configuration
        config = {
            "forge": {
                "path": str(forge_path),
                "port": 7860,
                "auto_start": True,
                "startup_timeout": 300,
                "api_enabled": True,
                "nowebui": True
            },
            "generation": {
                "width": 512,
                "height": 512,
                "steps": 25,
                "cfg_scale": 7.0,
                "sampler": "Euler a",
                "seed": -1,
                "negative_prompt": "blurry, bad quality, deformed, ugly"
            }
        }
        
        # Save app configuration
        config_path = Path("storybook_config.json")
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"\nSUCCESS: Configuration saved to: {config_path}")
        
        return forge_path
        
    except Exception as e:
        print(f"\nWARNING: GUI setup failed: {e}")
        return _setup_forge_cli()

def _setup_forge_cli():
    """Command-line fallback setup"""
    print("\nCommand-line setup:")
    
    while True:
        path_input = input("\nEnter Forge UI path (or 'q' to quit): ").strip()
        
        if path_input.lower() == 'q':
            return None
        
        forge_path = Path(path_input).expanduser().absolute()
        
        if _validate_forge_path(forge_path):
            return forge_path
        else:
            print(f"ERROR: Invalid path. Please check: {forge_path}")
            print("Ensure it contains webui.py, a launch script, and models/ folder.")
            print("For portable versions, try the 'webui' subfolder.")

def _validate_forge_path(path: Path) -> bool:
    """Robust validation for Windows paths"""
    if not path.exists():
        return False
    
    # Check for webui.py
    has_webui_py = (path / "webui.py").exists()
    
    # Check multiple possible launch scripts
    launch_scripts = ["webui.bat", "run.bat", "webui-user.bat", "run.py", "launch.py"]
    has_any_launcher = any((path / script).exists() for script in launch_scripts)
    
    # Check for models directory
    has_models = (path / "models").exists()
    
    return has_webui_py and has_any_launcher and has_models

def check_system_requirements():
    """Check basic system requirements"""
    print("\nChecking system requirements...")
    
    # Check Python
    try:
        import sys
        version = sys.version_info
        if version.major == 3 and version.minor >= 8:
            print(f"SUCCESS: Python {version.major}.{version.minor}.{version.micro}")
        else:
            print(f"ERROR: Python 3.8+ required (found {version.major}.{version.minor})")
            return False
    except:
        print("ERROR: Cannot determine Python version")
        return False
    
    # Check disk space (rough estimate)
    try:
        import shutil
        free_gb = shutil.disk_usage(Path.cwd()).free / (1024**3)
        if free_gb > 5:
            print(f"SUCCESS: Disk space: {free_gb:.1f} GB free")
        else:
            print(f"WARNING: Low disk space: {free_gb:.1f} GB (10+ GB recommended)")
    except:
        print("WARNING: Cannot check disk space")
    
    return True

def configure_forge(forge_path: Path):
    """Configure Forge settings via JSON files"""
    project_root = Path(__file__).parent
    output_dir = str(project_root / "generated_images")

    # Portable builds keep config.json/ui-config.json inside a webui subfolder.
    webui_dir = forge_path / "webui"
    settings_root = webui_dir if webui_dir.exists() else forge_path

    # Edit config.json for output dir and default model
    config_path = settings_root / "config.json"
    if not config_path.exists():
        print(f"WARNING: config.json not found at {config_path}. Creating new.")
        config = {}
    else:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

    # Set output directory
    config["outdir_txt2img_samples"] = output_dir
    config["outdir_img2img_samples"] = output_dir

    # Select and set default model
    default_model = _select_default_model(forge_path)
    if default_model:
        config["sd_model_checkpoint"] = default_model

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

    print(f"Updated config.json with output dir: {output_dir}")
    if default_model:
        print(f"Set default model: {default_model}")

    # Edit ui-config.json for generation defaults
    ui_config_path = settings_root / "ui-config.json"
    if not ui_config_path.exists():
        print(f"WARNING: ui-config.json not found at {ui_config_path}. Skipping UI defaults.")
        return

    with open(ui_config_path, 'r', encoding='utf-8') as f:
        ui_config = json.load(f)

    # Set UI defaults from storybook_config generation params
    app_config_path = project_root / "storybook_config.json"
    if app_config_path.exists():
        with open(app_config_path, 'r', encoding='utf-8') as f:
            app_config = json.load(f)
        gen = app_config.get("generation", {})

        ui_config["txt2img/Width/value"] = gen.get("width", 512)
        ui_config["txt2img/Height/value"] = gen.get("height", 512)
        ui_config["txt2img/Steps/value"] = gen.get("steps", 25)
        ui_config["txt2img/CFG Scale/value"] = gen.get("cfg_scale", 7.0)
        ui_config["txt2img/Sampler/value"] = gen.get("sampler", "Euler a")
        ui_config["txt2img/Seed/value"] = gen.get("seed", -1)
        ui_config["txt2img/Negative prompt/value"] = gen.get("negative_prompt", "blurry, bad quality, deformed, ugly")

    with open(ui_config_path, 'w', encoding='utf-8') as f:
        json.dump(ui_config, f, indent=2)
    
    print("Updated ui-config.json with default generation settings.")

def _select_default_model(forge_path: Path) -> str:
    """Prompt user to select default safetensors model"""
    # Portable builds keep models inside a webui subfolder.
    webui_dir = forge_path / "webui"
    search_root = webui_dir if webui_dir.exists() else forge_path
    models_dir = search_root / "models" / "Stable-diffusion"
    if not models_dir.exists():
        print("WARNING: No models/Stable-diffusion folder found. Skipping default model selection.")
        return ""
    
    models = [f.name for f in models_dir.glob("*.safetensors") if f.is_file()]
    if not models:
        print("WARNING: No .safetensors models found in models/Stable-diffusion. Download some first.")
        return ""
    
    print("\nAvailable Stable Diffusion models:")
    for i, model in enumerate(models, 1):
        print(f"{i}. {model}")
    
    while True:
        choice = input("\nSelect default model number (or Enter to skip): ").strip()
        if not choice:
            return ""
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
            else:
                print("Invalid selection. Try again.")
        except ValueError:
            print("Invalid input. Enter a number.")

def main():
    """Main setup routine"""
    print("=" * 60)
    print("STORYFORGE - FORGE UI SETUP")
    print("=" * 60)
    
    # Check requirements
    if not check_system_requirements():
        print("\nERROR: System requirements not met.")
        input("Press Enter to exit...")
        return False
    
    # Setup Forge UI
    forge_path = setup_forge_interactive()
    
    if not forge_path:
        print("\nERROR: Setup incomplete.")
        print("\nYou can manually create storybook_config.json with:")
        print('''{
  "forge": {
    "path": "C:\\\\path\\\\to\\\\your\\\\forge-ui",
    "port": 7860,
    "auto_start": true
  }
}''')
        input("\nPress Enter to exit...")
        return False
    
    # Configure Forge settings
    configure_forge(forge_path)
    
    print("\nSUCCESS: Setup complete! You're ready to create storybooks!")
    print("\nNext steps:")
    print("1. Make sure you have Stable Diffusion models in:")
    print(f"   {forge_path}\\models\\Stable-diffusion\\")
    print("2. Run: python storybookgui.py")
    print("\nNote: First launch may take 2-5 minutes to start Forge UI.")
    
    input("\nPress Enter to exit...")
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: Setup error: {e}")
        input("Press Enter to exit...")
        sys.exit(1)