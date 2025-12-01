FROM ubuntu:24.04

ARG INSTALL_DRIVER_VERSION="25.31.34666"
ENV http_proxy=http://proxy-mu.intel.com:911
ENV https_proxy=http://proxy-mu.intel.com:912
ENV HTTP_PROXY=http://proxy-mu.intel.com:911
ENV HTTPS_PROXY=http://proxy-mu.intel.com:912
ENV no_proxy=localhost,127.0.0.0/8,::1,10.224.90.1/24,localhost,virt-api,.svc,.svc.cluster.local,cdi-api,127.0.0.1,10.96.0.0/12,10.32.0.0/12,10.16.0.0/16,100.64.0.0/16,10.96.0.0/12
ENV NO_PROXY=localhost,127.0.0.0/8,::1,10.224.90.1/24,localhost,virt-api,.svc,.svc.cluster.local,cdi-api,127.0.0.1,10.96.0.0/12,10.32.0.0/12,10.16.0.0/16,100.64.0.0/16,10.96.0.0/12


RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    python3-pip \
    curl \
    wget \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app    
# Install Poetry globally

RUN pip install poetry --break-system-packages

# Copy project metadata and install deps
COPY ./lp-vlm/microservices/vlm/pyproject.toml ./lp-vlm/microservices/vlm/poetry.lock /app/
RUN poetry install --no-root

ARG COPYLEFT_SOURCES=false
RUN if [ "$COPYLEFT_SOURCES" = "true" ]; then \
        apt-get update && \
        # Get list of installed deb packages with copyleft licenses \
        sed -Ei 's/# deb-src /deb-src /' /etc/apt/sources.list && \
        apt-get update && \
        mkdir -p /copyleft_sources/deb && cd /copyleft_sources/deb && \
        echo -n $null > copyleft_package_list.txt && \
        for package in $(dpkg -l | awk '/^ii/ {print $2}' | cut -d: -f1); do \
            grep -l 'Copyleft\|GPL\|LGPL\|EPL\|MPL\|CDDL' /usr/share/doc/${package}/copyright; \
            exit_status=$?; \
            if [ $exit_status -eq 0 ]; then \
                echo $package >> copyleft_package_list.txt; \
                apt-get source -q --download-only $package; \
            fi; \
        done; \
        # Get source code for installed Python packages with copyleft licenses \
        mkdir -p /copyleft_sources/python && \
        cd /copyleft_sources/python && \
        apt-get update && apt-get install -y gcc build-essential libffi-dev python3-dev && \
        # Download python package sources with relevant licenses \
        pip3 freeze | cut -d= -f1 | while read pkg; do \
            meta=$(pip3 show $pkg 2>/dev/null); \
            lic=$(echo "$meta" | grep -i '^License:' | grep -E 'MPL|GPL|General Public License|EPL|Eclipse Public License|CDDL|LGPL'); \
            if [ ! -z "$lic" ]; then \
                echo "Downloading source for $pkg with license: $lic"; \
                pip3 download --no-binary :all: $pkg || true; \
            fi; \
        done; \
        apt-get remove --purge -y gcc build-essential libffi-dev python3-dev; \
    fi



# Copy source code and scripts
COPY ./lp-vlm/microservices/vlm/scripts ./scripts
COPY ./lp-vlm/microservices/vlm/src ./src
COPY ./lp-vlm/microservices/vlm/poetry.lock .
COPY ./lp-vlm/microservices/vlm/pyproject.toml .
RUN chmod +x /app/scripts/compress_model.sh

# Install Intel GPU drivers
COPY ./lp-vlm/microservices/vlm/scripts/install_ubuntu_gpu_drivers.sh /tmp/install_gpu_drivers.sh
RUN chmod +x /tmp/install_gpu_drivers.sh && /tmp/install_gpu_drivers.sh ${INSTALL_DRIVER_VERSION}

# Clean up
RUN apt-get clean && rm -rf /tmp/install_gpu_drivers.sh /var/lib/apt/lists/* /tmp/* /root/.cachetmp/*

# Create cache and model directories
RUN mkdir -p /root/.cache/huggingface /app/ov-model

EXPOSE 8000

# Run compression + app
CMD ["/bin/bash", "-c", "/app/scripts/compress_model.sh ${VLM_MODEL_NAME} ${VLM_COMPRESSION_WEIGHT_FORMAT} ${HUGGINGFACE_TOKEN} && poetry run gunicorn -b 0.0.0.0:8000 -k uvicorn.workers.UvicornWorker src.app:app --timeout 10000 -w ${WORKERS:-1} --log-level ${VLM_OPENVINO_LOG_LEVEL:-info} --access-logfile ${VLM_ACCESS_LOG_FILE:--} --error-logfile -"]
