# hypertrainer-ai-toolkit-runpod-worker

An AI toolkit Runpod worker

## Getting started

- Set the following environment variables to GitHub actions:
  - `DOCKERHUB_IMG`

## How it works

- The image is based on the Pytorch 2.4.1 image with CUDA 12.4 and cuDNN 9.0.
- The script will try to download the dataset from the given URL then unzip it
- Will decode the base64 encoded config and save it as `config.yaml` into the `ai-toolkit/config` folder

## How to use

- When deployed, it expects a payload with the following schema:

```
{
    "config": "..." # A bas64 encode YAML with the ai-toolkit config
    "dataset_url": "..." # The URL pointing to the dataset, it should be a .zip file containing the images and captions
    "task_id": "..." # An id that represents the task, used to identify each task via webhook and to store the output
}
```

> Note: The worker will override the following values:

```python
overrides = {
    'config.name': 'lora',
    'config.process.0.training_folder': 'output',
    'config.process.0.datasets.0.folder_path': 'dataset'
}
```

## How to deploy

- Choose an image from the GitHub Container Registry
- Deploy the image to RunPod via Serverless Workers, deploy it on at least an A100 80GB
- Set at least 100gb of container storage
- Set the following environment variables:
  - `R2_ACCESS_KEY`
  - `R2_SECRET_ACCESS_KEY`
  - `R2_ENDPOINT`
  - `R2_PUBLIC_URL`
  - `R2_BUCKET_NAME`
  - `HF_TOKEN`

## ToDo

- Add a way to specify to load a local model via network volumes
- Reset worker after training is done
  - Empty the `ai-toolkit/output` folder
  - Delete the `ai-toolkit/dataset` folder
  - Empty the `ai-toolkit/config` folder
- Rename `DOCKERHUB_IMG` to something else, since we're not using Docker Hub anymore

## Credits

- Full creditst Ostris for the `ai-toolkit` codebase 🙏
