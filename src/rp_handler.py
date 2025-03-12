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

            print("Launching training script")
            try:
                # Log in to Hugging Face CLI
                hf_token = os.environ.get('HF_TOKEN')
                if not hf_token:
                    raise ValueError("HF_TOKEN environment variable is not set")
                
                print("Logging in to Hugging Face CLI")
                subprocess.run(['huggingface-cli', 'login', '--token', hf_token], check=True)
                print("Successfully logged in to Hugging Face CLI")

                # Run the training script
                subprocess.run(['python', 'ai-toolkit/run.py', 'ai-toolkit/config/config.yaml'], check=True)
                
                result = InferenceResult(
                    ok=True,
                    message="Training run completed successfully"
                )
                model_path = 'ai-toolkit/output/lora/lora.safetensors'
                if os.path.exists(model_path):
                    print(f"Model file found at {model_path}")
                    bucket_name = os.environ.get('R2_BUCKET_NAME')
                    object_name = f"{OUTPUT_R2_FOLDER}/{job_id}/{job_id}.safetensors"
                    print(f"Uploading model to R2: {bucket_name}/{object_name}")
                    uploaded_url = upload_to_r2(model_path, bucket_name, object_name)
                    
                    if uploaded_url:
                        result.model_url = uploaded_url
                        print(f"Model uploaded successfully: {uploaded_url}")
                    else:
                        result.message += " (Failed to upload model file)"
                        print("Failed to upload model file")
                else:
                    result.message += " (Model file not found)"
                    print(f"Model file not found at {model_path}")
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
