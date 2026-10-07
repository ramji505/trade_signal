#!/usr/bin/env bash
# ==============================================================================
# TradeSignal India - EC2 Initial Server Setup Script
# Run this once on your Amazon Linux 2023 / Ubuntu EC2 instance:
#   chmod +x scripts/setup_ec2.sh && ./scripts/setup_ec2.sh
# ==============================================================================

set -e

echo "🛠️ Updating packages..."
if [ -f /etc/amazon-linux-release ]; then
    sudo dnf update -y
    sudo dnf install -y docker git
    sudo systemctl start docker
    sudo systemctl enable docker
    sudo usermod -aG docker $USER
elif [ -f /etc/lsb-release ]; then
    sudo apt-get update -y
    sudo apt-get install -y ca-certificates curl gnupg lsb-release
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker $USER
fi

echo "📁 Creating project working directories..."
mkdir -p ~/trade-signal-india_v2_upgrade

echo "✅ Docker & Server Setup Complete! Log out and log back in to apply docker group permissions."
