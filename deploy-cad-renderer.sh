#!/bin/bash
# Deploy CAD renderer from GitHub to asset server

set -e

echo "==================================="
echo "CAD Renderer Deployment Script"
echo "==================================="
echo ""

# Configuration
GITHUB_REPO="https://github.com/dceballos/cad_renderer.git"
ASSET_SERVER="10.100.2.20"
DEPLOY_USER="deploy"
GIT_REMOTE="deploy@${ASSET_SERVER}:git/cad_renderer.git"
TEMP_DIR="/tmp/cad_renderer_deploy_$$"

echo "1. Cloning repository from GitHub..."
git clone $GITHUB_REPO $TEMP_DIR

cd $TEMP_DIR

echo ""
echo "2. Adding asset server as remote..."
git remote add production $GIT_REMOTE

echo ""
echo "3. Setting up main branch for production..."
git checkout -b main
git push production main --force

echo ""
echo "4. Cleaning up temporary directory..."
cd /
rm -rf $TEMP_DIR

echo ""
echo "==================================="
echo "Deployment complete!"
echo "==================================="
echo ""
echo "The CAD renderer has been deployed to the asset server."
echo "The post-receive hook will:"
echo "  - Extract the code to a new release directory"
echo "  - Install Python dependencies"
echo "  - Update the current symlink"
echo "  - Restart the cad-renderer service"
echo ""
echo "You can verify the deployment by checking:"
echo "  - http://cad-proxy.eswindows.co/v3/cad"
echo "  - http://cad-proxy.eswindows.co/v3/top-view"