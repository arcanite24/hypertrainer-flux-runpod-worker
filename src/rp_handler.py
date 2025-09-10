"""Module wrapper for Runpod serverless function"""

import os
import base64
import requests
import zipfile
import subprocess
from dataclasses import asdict
import yaml
import boto3
from botocore.client import Config
import shutil
import threading
import time

import runpod
from runpod.serverless.utils.rp_validator import validate
from models import InferenceResult, StandardResponse
from rp_schema import INPUT_SCHEMA

OUTPUT_R2_FOLDER = 'models'

def override_config(config_data, overrides):
    def update_nested(d, path, value):
        keys = path.split('.')
        for key in keys[:-1]:
            if key.isdigit():
                key = int(key)
            if key not in d:
                d[key] = {}
            d = d[key]
        last_key = keys[-1]
        if last_key.isdigit():
            last_key = int(last_key)
        d[last_key] = value

    # Load the YAML data
    config = yaml.safe_load(config_data)

    # Apply overrides
    for path, value in overrides.items():
        update_nested(config, path, value)

    # Convert back to YAML
    return yaml.dump(config, default_flow_style=False)

def upload_to_r2(file_path, bucket_name, object_name):
    s3 = boto3.client('s3',
        endpoint_url=os.environ['R2_ENDPOINT'],
        aws_access_key_id=os.environ['R2_ACCESS_KEY'],
        aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )
    
    try:
        s3.upload_file(file_path, bucket_name, object_name)
        url = f"{os.environ['R2_PUBLIC_URL']}/{object_name}"
        return url
    except Exception as e:
        print(f"Failed to upload file to R2: {str(e)}")
        return None

def cleanup_workspace():
    print("Cleaning up workspace...")
    
    # Empty the ai-toolkit/output folder
    for root, dirs, files in os.walk('ai-toolkit/output'):
        for file in files:
            os.remove(os.path.join(root, file))
    
    # Delete the ai-toolkit/dataset folder
    if os.path.exists('ai-toolkit/dataset'):
        shutil.rmtree('ai-toolkit/dataset')
    
    # Delete the ai-toolkit/control folder
    if os.path.exists('ai-toolkit/control'):
        shutil.rmtree('ai-toolkit/control')
    
    # Empty the ai-toolkit/config folder
    for root, dirs, files in os.walk('ai-toolkit/config'):
        for file in files:
            os.remove(os.path.join(root, file))
    
    print("Workspace cleaned up successfully")

def send_webhook_notification(webhook_url, job_id, notification_type, payload=None):
    """
    Send a webhook notification to the specified URL.
    
    Args:
        webhook_url (str): The URL to send the webhook to
        job_id (str): The ID of the job
        notification_type (str): The type of notification (e.g., 'start', 'complete', 'error')
        payload (dict, optional): Additional data to include in the webhook. Defaults to empty dict.
    
    Returns:
        bool: True if the webhook was sent successfully, False otherwise
    """
    if not webhook_url:
        print("No webhook URL provided, skipping notification")
        return False
    
    if payload is None:
        payload = {}
    
    webhook_data = {
        "type": notification_type,
        "job_id": job_id,
        "payload": payload
    }
    
    try:
        print(f"Sending {notification_type} webhook notification for job {job_id}")
        response = requests.post(webhook_url, json=webhook_data, timeout=30)
        
        if response.status_code >= 200 and response.status_code < 300:
            print(f"Webhook notification sent successfully: {response.status_code}")
            return True
        else:
            print(f"Webhook notification failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"Error sending webhook notification: {str(e)}")
        return False

def run(job):
    '''
    Run the training task
    '''
    print("Starting job execution")
    job_input = job['input']

    # Input validation
    print("Validating input")
    validated_input = validate(job_input, INPUT_SCHEMA)

    if 'errors' in validated_input:
        print(f"Input validation failed: {validated_input['errors']}")
        return asdict(StandardResponse(results=[InferenceResult(ok=False, error=str(validated_input['errors']))]))
    validated_input = validated_input['validated_input']

    job_id = validated_input['job_id']
    
    webhook_url = validated_input['webhook_url']
    use_webhook = False

    if webhook_url:
        use_webhook = True
        print(f"Webhook URL provided: {webhook_url}")

    try:
        print("Decoding and writing config")
        config_data = base64.b64decode(validated_input['config']).decode('utf-8')
        
        os.makedirs('ai-toolkit/config', exist_ok=True)
        with open('ai-toolkit/config/config.yaml', 'w', encoding='utf-8') as f:
            f.write(config_data)
        print("Config written successfully")

        print(yaml.safe_dump(yaml.safe_load(config_data), indent=4))

        print(f"Downloading dataset from {validated_input['dataset_url']}")
        response = requests.get(validated_input['dataset_url'], timeout=4096)
        if response.status_code == 200:
            with open('dataset.zip', 'wb') as f:
                f.write(response.content)
            print("Dataset downloaded successfully")

            print("Unzipping dataset")
            os.makedirs('ai-toolkit/dataset', exist_ok=True)
            with zipfile.ZipFile('dataset.zip', 'r') as zip_ref:
                zip_ref.extractall('ai-toolkit/dataset')
            print("Dataset unzipped successfully")

            # Handle optional control_url
            if 'control_url' in validated_input and validated_input['control_url']:
                print(f"Downloading control data from {validated_input['control_url']}")
                control_response = requests.get(validated_input['control_url'], timeout=4096)
                if control_response.status_code == 200:
                    with open('control.zip', 'wb') as f:
                        f.write(control_response.content)
                    print("Control data downloaded successfully")

                    print("Unzipping control data")
                    os.makedirs('ai-toolkit/control', exist_ok=True)
                    with zipfile.ZipFile('control.zip', 'r') as zip_ref:
                        zip_ref.extractall('ai-toolkit/control')
                    print("Control data unzipped successfully")
                else:
                    print(f"Failed to download control data. Status code: {control_response.status_code}")
                    raise Exception(f"Failed to download control data. Status code: {control_response.status_code}")
            else:
                print("No control_url provided, skipping control data download")

            print("Launching training script")
            try:
                # Setup shared tracking for uploaded files and start monitoring
                uploaded_files = set()
                stop_event = None
                monitor_thread = None
                
                def monitor_and_upload(folder, bucket, prefix, stop_event, uploaded_files):
                    while not stop_event.is_set():
                        try:
                            if os.path.isdir(folder):
                                for fname in os.listdir(folder):
                                    if fname.endswith('.safetensors') and fname not in uploaded_files:
                                        file_path = os.path.join(folder, fname)
                                        object_name = f"{prefix}/{fname}"
                                        url = upload_to_r2(file_path, bucket, object_name)
                                        if url:
                                            print(f"Uploaded {fname} to {url}")
                                        uploaded_files.add(fname)
                        except Exception as e:
                            print(f"Error in monitor_and_upload: {str(e)}")
                        time.sleep(5)
                
                bucket_name = os.environ.get('R2_BUCKET_NAME')
                folder = 'ai-toolkit/output/lora'
                prefix = f"{OUTPUT_R2_FOLDER}/{job_id}"
                if bucket_name:
                    stop_event = threading.Event()
                    monitor_thread = threading.Thread(
                        target=monitor_and_upload,
                        args=(folder, bucket_name, prefix, stop_event, uploaded_files),
                        daemon=True
                    )
                    monitor_thread.start()
                    
                # Log in to Hugging Face CLI
                hf_token = os.environ.get('HF_TOKEN')
                if not hf_token:
                    raise ValueError("HF_TOKEN environment variable is not set")
                
                print("Logging in to Hugging Face CLI")
                subprocess.run(['huggingface-cli', 'login', '--token', hf_token], check=True)
                print("Successfully logged in to Hugging Face CLI")

                # Run the training script
                subprocess.run(['python', 'ai-toolkit/run.py', 'ai-toolkit/config/config.yaml'], check=True)
                # Final scan to upload any remaining .safetensors files
                if bucket_name:
                    for fname in os.listdir(folder):
                        if fname.endswith('.safetensors') and fname not in uploaded_files:
                            file_path = os.path.join(folder, fname)
                            object_name = f"{prefix}/{fname}"
                            url = upload_to_r2(file_path, bucket_name, object_name)
                            if url:
                                print(f"Final upload: Uploaded {fname} to {url}")
                            uploaded_files.add(fname)
                # Stop background monitoring after training completes
                if bucket_name and stop_event is not None and monitor_thread is not None:
                    stop_event.set()
                    monitor_thread.join()
                result = InferenceResult(
                    ok=True,
                    message="Training run completed successfully"
                )
            except subprocess.CalledProcessError as e:
                print(f"Command failed with exit code {e.returncode}")
                raise Exception(f"Command failed with exit code {e.returncode}. Error: {e.output}")

        else:
            print(f"Failed to download dataset. Status code: {response.status_code}")
            raise Exception(f"Failed to download dataset. Status code: {response.status_code}")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
        result = InferenceResult(
            ok=False,
            error=str(e)
        )

    print("Job execution completed")

    if use_webhook:
        send_webhook_notification(webhook_url, job_id, 'COMPLETED')

    cleanup_workspace()
    return asdict(StandardResponse(results=[result]))

if __name__ == "__main__":
    runpod.serverless.start({"handler": run})
