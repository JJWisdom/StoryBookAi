import subprocess
import threading
import time
import logging
import requests
import os
import signal
import psutil

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - forge_handler - %(levelname)s - %(message)s"
)

class ForgeHandler:
    """
    Handles launching and communicating with Forge Portable
    using run.bat (the correct entry point).
    """

    def __init__(self, forge_root=None, port=7860):
        self.port = port
        self.forge_root = forge_root or os.path.join(
            os.getcwd(),
            "webui_forge_cu121_torch231"
        )

        self.process = None
        self.stdout_thread = None
        self.running = False
        self.startup_complete = False

        self.api_url = f"http://127.0.0.1:{self.port}"

        self.runbat_path = os.path.join(self.forge_root, "run.bat")
        if not os.path.exists(self.runbat_path):
            raise FileNotFoundError(f"run.bat not found at: {self.runbat_path}")

    # ------------------------------------------------------------
    # Internal: Listen to Forge Output
    # ------------------------------------------------------------
    def _read_stdout(self):
        logging.info("Forge stdout thread started")
        startup_indicators = [
            "Running on local URL",
            f":{self.port}",
            "Model selected",
            "Application startup complete",
            "Uvicorn running",
            "Startup time:"
        ]
        
        for line in iter(self.process.stdout.readline, ""):
            if line:
                text = line.strip()
                logging.info(f"Forge: {text}")
                
                # Multiple indicators that Forge is ready
                for indicator in startup_indicators:
                    if indicator in text:
                        logging.info(f"Detected Forge ready indicator: {indicator}")
                        self.running = True
                        self.startup_complete = True
                        break
                        
        logging.info("Forge output stream ended.")

    # ------------------------------------------------------------
    # Start Forge Portable
    # ------------------------------------------------------------
    def start_forge(self):
        if self.process and self.running:
            logging.info("Forge already running.")
            return True

        logging.info(f"Starting Forge at: {self.runbat_path}")

        # Always run from the root folder of the portable build
        self.process = subprocess.Popen(
            [
                "cmd.exe",
                "/c",
                "run.bat",
                "--api",
                "--nowebui",
                "--port",
                str(self.port),
                "--no-open",               # Don't open browser
                "--disable-console-progressbars",  # Cleaner output
                "--skip-torch-cuda-test",  # Skip CUDA test (already done)
                "--listen"   
            ],
            cwd=self.forge_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            bufsize=1,
            universal_newlines=True
        )

        # Thread to read stdout
        self.stdout_thread = threading.Thread(
            target=self._read_stdout,
            daemon=True
        )
        self.stdout_thread.start()

        logging.info("Waiting for Forge API to become available...")
        
        # Wait a bit for the process to start
        time.sleep(5)

        # Try to wait for Forge to be ready with multiple methods
        for attempt in range(60):  # 60 * 5 = 300 seconds total
            try:
                # Method 1: Check if process is still alive
                if self.process.poll() is not None:
                    logging.error("Forge process died unexpectedly")
                    return False
                
                # Method 2: Try to ping the API
                try:
                    response = requests.get(f"{self.api_url}/sdapi/v1/sd-models", timeout=2)
                    if response.status_code == 200:
                        logging.info("Forge API is online and responding!")
                        self.running = True
                        self.startup_complete = True
                        return True
                except requests.exceptions.RequestException:
                    pass
                
                # Method 3: Check if stdout thread detected ready signal
                if self.running and self.startup_complete:
                    logging.info("Forge marked as ready by stdout detection")
                    return True
                
                # Method 4: Check if we've been waiting too long
                if attempt > 30:  # After 150 seconds
                    logging.warning(f"Forge taking a long time to start... (attempt {attempt+1}/60)")
                    
                time.sleep(5)
                
            except Exception as e:
                logging.error(f"Error checking Forge status: {e}")
                time.sleep(5)

        logging.error("Forge did not start within timeout.")
        return False

    # ------------------------------------------------------------
    # Check if Forge is actually responding
    # ------------------------------------------------------------
    def check_forge_ready(self):
        """Check if Forge API is actually responding"""
        if not self.running:
            return False
            
        try:
            # Try a simple API call
            response = requests.get(f"{self.api_url}/sdapi/v1/sd-models", timeout=10)
            return response.status_code == 200
        except:
            return False

    # ------------------------------------------------------------
    # Stop Forge
    # ------------------------------------------------------------
    def stop_forge(self):
        if not self.process:
            logging.info("Forge is not running.")
            return

        logging.info("Stopping Forge...")
        self.running = False
        self.startup_complete = False

        try:
            os.kill(self.process.pid, signal.SIGTERM)
        except OSError as e:
            logging.warning("SIGTERM failed (%s), falling back to terminate()", e)
            try:
                self.process.terminate()
            except OSError as e2:
                logging.error("terminate() also failed: %s", e2)

        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()

        self.process = None
        logging.info("Forge stopped.")

    # ------------------------------------------------------------
    # Send prompt → generate image → return image path
    # ------------------------------------------------------------
    def generate_image(self, prompt, output_dir="generated_images",
                       width=512, height=512, steps=25, cfg_scale=7.0,
                       sampler_name="Euler a",
                       negative_prompt="blurry, bad quality, deformed, ugly, disfigured",
                       seed=-1, request_timeout=180):
        # Double-check Forge is actually responding
        if not self.check_forge_ready():
            raise RuntimeError("Forge is not running or not responding to API.")

        os.makedirs(output_dir, exist_ok=True)

        payload = {
            "prompt": prompt,
            "steps": steps,
            "width": width,
            "height": height,
            "cfg_scale": cfg_scale,
            "sampler_name": sampler_name,
            "negative_prompt": negative_prompt,
            "seed": seed,
        }

        logging.info(f"Sending prompt to Forge: {prompt[:100]}...")

        try:
            r = requests.post(
                f"{self.api_url}/sdapi/v1/txt2img",
                json=payload,
                timeout=request_timeout,
            )
        except requests.exceptions.RequestException as e:
            logging.error(f"Forge request failed: {e}")
            return None

        if r.status_code != 200:
            logging.error(f"Forge returned status {r.status_code}: {r.text[:200]}")
            return None

        data = r.json()
        if "images" not in data or not data["images"]:
            logging.error("Forge did not return an image.")
            return None

        # Save the base64 image
        import base64
        image_b64 = data["images"][0]
        image_bin = base64.b64decode(image_b64)

        filename = f"forge_{int(time.time())}.png"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "wb") as f:
            f.write(image_bin)

        logging.info(f"Image saved: {filepath}")
        return filepath
    


    def shutdown(self):
        """Terminate Forge and all child processes via psutil."""
        if self.process is None:
            return

        self.running = False
        self.startup_complete = False

        try:
            proc = psutil.Process(self.process.pid)
            for child in proc.children(recursive=True):
                try:
                    child.kill()
                except OSError:
                    pass
            proc.kill()
        except Exception as e:
            logging.error(f"Error shutting down Forge: {e}")
        finally:
            self.process = None



# ----------------------------------------------------------------
# Debug / Manual Run
# ----------------------------------------------------------------
if __name__ == "__main__":
    forge = ForgeHandler()
    if forge.start_forge():
        print("Forge started successfully.")
        print(f"API URL: {forge.api_url}")
        # Test with a simple prompt
        test_prompt = "a cute cat"
        print(f"Testing with prompt: {test_prompt}")
        result = forge.generate_image(test_prompt)
        if result:
            print(f"Success! Image saved to: {result}")
        else:
            print("Failed to generate image")
    else:
        print("Failed to start Forge.")