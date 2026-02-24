#!/usr/bin/env bash
set -euo pipefail

echo "This script is deprecated."
echo "The AI stack now deploys via K3s + Kustomize/Skaffold and expects images to be"
echo "built/pushed to a registry (local or remote) instead of importing from a local"
echo "container engine cache."
echo ""
echo "Suggested paths:"
echo "  1) Use skaffold: skaffold run -p dev"
echo "  2) Push images to your registry and update kustomize overlays"
echo ""
echo "See DEPLOYMENT.md for the K3s-only workflow."
exit 1
