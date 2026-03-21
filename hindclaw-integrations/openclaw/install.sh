#!/bin/bash
set -e

echo "Installing HindClaw Memory Plugin for OpenClaw..."

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INSTALL_DIR="$HOME/.openclaw/extensions/hindclaw"

# Check Node version
if ! command -v node &> /dev/null; then
    echo "Error: Node.js not found. Please install Node.js 22+"
    exit 1
fi

# Build the plugin
echo "Building plugin..."
cd "$SCRIPT_DIR"
npm install
npm run build

# Deploy to OpenClaw extensions
echo "Deploying to $INSTALL_DIR..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copy files
cp -r dist package.json openclaw.plugin.json README.md "$INSTALL_DIR/"

# Install dependencies in deployed location
echo "Installing dependencies..."
cd "$INSTALL_DIR"
npm install --omit=dev

echo ""
echo "HindClaw Memory Plugin installed successfully!"
echo ""
echo "Next steps:"
echo ""
echo "1. Configure your LLM provider (e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY)"
echo ""
echo "2. Enable the plugin:"
echo "   openclaw plugins enable hindclaw"
echo ""
echo "3. Start OpenClaw:"
echo "   openclaw gateway"
echo ""
