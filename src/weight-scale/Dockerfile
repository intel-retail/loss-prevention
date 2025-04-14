#
# Copyright (C) 2024-25 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .

# Install dependencies from the requirements file
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "weight-scale.py"]
