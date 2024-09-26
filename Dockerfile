FROM pytorch/pytorch:2.4.1-cuda12.4-cudnn9-runtime

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

WORKDIR /

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash
ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/lib/x86_64-linux-gnu

# Update and upgrade the system packages (Worker Template)
RUN apt-get update -y && \
    apt-get upgrade -y && \
    apt-get install --yes --no-install-recommends \
    build-essential \
    vim \
    git \
    wget \
    software-properties-common \
    google-perftools \
    curl \
    bash \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY builder/requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt && \
    rm /requirements.txt

# Clone toolkit
RUN git clone https://github.com/arcanite24/hyper-ai-toolkit.git ai-toolkit && \
    cd ai-toolkit && \
    git submodule update --init --recursive

# Add src files (Worker Template)
ADD src .

ENV RUNPOD_DEBUG_LEVEL=INFO

CMD python -u /rp_handler.py