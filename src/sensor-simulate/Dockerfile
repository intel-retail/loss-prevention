#
# Copyright (C) 2025 Intel Corporation.
#
# SPDX-License-Identifier: Apache-2.0
#
FROM python:3.13-slim

WORKDIR /

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY sensor-simulate.py sensor-simulate.py

CMD ["python3", "-u", "sensor-simulate.py", "-f", "sample-file.txt"]
