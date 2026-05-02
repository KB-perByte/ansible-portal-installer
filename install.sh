#!/bin/bash
#
# Quick installation script for Ansible Portal Installer
#

set -e

echo "=========================================="
echo "Ansible Portal Installer - Setup"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python: $python_version"

# Check if Python 3.10+
required_version="3.10"
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)"; then
    echo "ERROR: Python 3.10 or higher is required"
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "✓ pip upgraded"

# Install package
echo ""
echo "Installing ansible-portal-installer..."
pip install -e ".[dev]" > /dev/null 2>&1
echo "✓ Package installed"

# Setup .env if needed
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your configuration!"
    echo "   vim .env"
else
    echo "✓ .env file already exists"
fi

# Verify installation
echo ""
echo "Verifying installation..."
if command -v ansible-portal-installer &> /dev/null; then
    version=$(ansible-portal-installer --version 2>&1)
    echo "✓ $version"
else
    echo "✗ Installation verification failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Activate virtual environment:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Configure environment:"
echo "     vim .env"
echo ""
echo "  3. Verify prerequisites:"
echo "     ansible-portal-installer verify"
echo ""
echo "  4. Run deployment:"
echo "     ansible-portal-installer full-deploy"
echo ""
echo "See README.md and SETUP.md for more information."
echo ""
