#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$SCRIPT_DIR"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

echo -e "${GREEN}=== Agent Lynkia Deployment ===${NC}\n"

# Step 1: Clean previous build
echo -e "${YELLOW}[1/4] Cleaning previous build...${NC}"
rm -rf "$AGENT_DIR/package"
rm -f "$AGENT_DIR/lambda.zip"

# Step 2: Create package directory and install dependencies
echo -e "${YELLOW}[2/4] Installing dependencies...${NC}"
mkdir -p "$AGENT_DIR/package"

# Use pip3 to install dependencies (Python 3.11 compatible)
pip3 install \
    --platform manylinux2014_x86_64 \
    --target "$AGENT_DIR/package" \
    --implementation cp \
    --python-version 3.11 \
    --only-binary=:all: \
    --upgrade \
    -r "$AGENT_DIR/requirements.txt" 2>/dev/null || \
pip3 install -r "$AGENT_DIR/requirements.txt" -t "$AGENT_DIR/package"

# Step 3: Copy application code
echo -e "${YELLOW}[3/4] Packaging Lambda function...${NC}"
cp -r "$AGENT_DIR/api" "$AGENT_DIR/package/"
cp -r "$AGENT_DIR/core" "$AGENT_DIR/package/"
cp -r "$AGENT_DIR/models" "$AGENT_DIR/package/"
cp -r "$AGENT_DIR/services" "$AGENT_DIR/package/"
cp "$AGENT_DIR/main.py" "$AGENT_DIR/package/"
cp "$AGENT_DIR/handler.py" "$AGENT_DIR/package/"

# Create ZIP
cd "$AGENT_DIR/package"
zip -r "$AGENT_DIR/lambda.zip" . -x "*.pyc" -x "__pycache__/*" -x "*.dist-info/*"
cd "$AGENT_DIR"

# Cleanup package directory
rm -rf "$AGENT_DIR/package"

# Copy lambda.zip to terraform directory
cp "$AGENT_DIR/lambda.zip" "$TERRAFORM_DIR/lambda.zip"

echo -e "${GREEN}Lambda package created: lambda.zip${NC}"
echo -e "Size: $(du -h "$TERRAFORM_DIR/lambda.zip" | cut -f1)\n"

# Step 4: Deploy with Terraform
echo -e "${YELLOW}[4/4] Deploying with Terraform...${NC}"

# Check if terraform.tfvars exists
if [ ! -f "$TERRAFORM_DIR/terraform.tfvars" ]; then
    echo -e "${RED}ERROR: terraform.tfvars not found!${NC}"
    echo -e "Please copy terraform.tfvars.example to terraform.tfvars and fill in your credentials:"
    echo -e "  cp $TERRAFORM_DIR/terraform.tfvars.example $TERRAFORM_DIR/terraform.tfvars"
    exit 1
fi

cd "$TERRAFORM_DIR"
terraform init -upgrade
terraform apply -auto-approve

echo -e "\n${GREEN}=== Deployment Complete ===${NC}\n"
echo -e "Next steps:"
echo -e "1. Copy the webhook_url from above"
echo -e "2. Go to Twilio Console → Messaging → WhatsApp Sandbox"
echo -e "3. Paste the URL in 'When a message comes in'"
echo -e "4. Send a WhatsApp message to test!\n"
