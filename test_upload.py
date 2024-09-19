import os
import boto3
from botocore.client import Config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Test file path
test_file_path = 'test_file.txt'

# Create a test file if it doesn't exist
if not os.path.exists(test_file_path):
    with open(test_file_path, 'w') as f:
        f.write('This is a test file for R2 upload.')

# Get R2 bucket name from environment variable
bucket_name = os.environ.get('R2_BUCKET_NAME')
if not bucket_name:
    raise ValueError("R2_BUCKET_NAME environment variable is not set")

# Set object name for the test upload
object_name = 'test_upload.txt'

print(f"Uploading {test_file_path} to R2 bucket: {bucket_name}")

# Create S3 client
s3 = boto3.client('s3',
    endpoint_url=os.environ['R2_ENDPOINT'],
    aws_access_key_id=os.environ['R2_ACCESS_KEY'],
    aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
    config=Config(signature_version='s3v4'),
    region_name='auto'
)

# Attempt to upload the file
try:
    s3.upload_file(test_file_path, bucket_name, object_name)
    url = f"{os.environ['R2_PUBLIC_URL']}/{object_name}"
    print(f"File uploaded successfully. URL: {url}")
except Exception as e:
    print(f"File upload failed. Error: {str(e)}")

# Clean up: remove the test file
os.remove(test_file_path)
print(f"Test file {test_file_path} removed.")