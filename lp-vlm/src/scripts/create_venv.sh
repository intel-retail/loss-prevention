#!/bin/bash
VENV_NAME="loss-prevention-venv"

# Check if virtual environment already exists
if [ -d "$LP_BASE_DIR/$VENV_NAME" ]; then
    echo "Virtual environment '$VENV_NAME' already exists. Skipping creation."
else
    echo "Creating virtual environment '$VENV_NAME'..."
    python3 -m venv $LP_BASE_DIR/$VENV_NAME
    echo "Virtual environment created successfully."
fi

# Install requirements if they exist
if [ -f "src/scripts/requirements.txt" ]; then
    echo "Installing requirements..."
    # Use the venv's pip directly (no need to activate)
    $LP_BASE_DIR/$VENV_NAME/bin/pip install -r src/scripts/requirements.txt
    echo "Requirements installed successfully."
fi

echo "Setup complete!"