import os
import requests
import json
import base64
import time
from dotenv import load_dotenv
from PIL import Image
import io

# Load environment variables from .env file
load_dotenv()
print("Environment variables loaded.")

# Get environment variables
RD_WORKER_ID = os.getenv("RD_WORKER_ID")
RD_API_KEY = os.getenv("RD_API_KEY")
YAML_PATH = "fast.yaml"
DATASET_URL = "https://pub-89d2ac1d5adb4dddbf689b440ebafdd2.r2.dev/50_svportrait64.zip"

print(f"Worker ID: {RD_WORKER_ID}")
print(f"YAML Path: {YAML_PATH}")

# API endpoint
url = f"https://api.runpod.ai/v2/{RD_WORKER_ID}/runsync"
print(f"API URL: {url}")

# Request headers
headers = {"Content-Type": "application/json", "Authorization": f"Bearer {RD_API_KEY}"}
print("Headers prepared.")

# Load and encode the YAML file
print(f"Loading YAML file from {YAML_PATH}...")
with open(YAML_PATH, 'rb') as yaml_file:
    yaml_content = yaml_file.read()
    yaml_base64 = base64.b64encode(yaml_content).decode('utf-8')
print("YAML file loaded and encoded.")
# Update payload with base64 encoded YAML
payload = {
    "input": {
        "config": yaml_base64,
        "dataset_url": DATASET_URL
    }
}
print("Payload prepared.")
print(payload)

# Measure time and send POST request
print("Sending POST request to API...")
start_time = time.time()
response = requests.post(url, json=payload, headers=headers, timeout=4096)
end_time = time.time()
print("API request completed.")

# Print response and time taken
print("\nResponse from API:")
response_json = response.json()
print(json.dumps(response_json, indent=2))
print(f"\nTime taken: {end_time - start_time:.2f} seconds")

print("\nDone")
