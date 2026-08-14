#!/usr/bin/env bash
# Build once locally and copy the immutable pack over the private LAN.
set -euo pipefail

root=/mnt/F/Obsidian
stamp=$(date +%Y%m%d_%H%M%S)
pack=/tmp/VIST_ResearchPack_${stamp}

python3 "$root/Vault/ResearchOps/deploy/build_research_pack.py" --output "$pack"
for target in 'ilex@192.168.10.101' 'yinzhe@192.168.10.1'; do
  ssh -i /home/ilex/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes "$target" 'mkdir -p ~/ResearchOps-VIST'
  rsync -a --checksum -e 'ssh -i /home/ilex/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes' "$pack/" "$target:~/ResearchOps-VIST/$stamp/"
  ssh -i /home/ilex/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes "$target" "ln -sfn ~/ResearchOps-VIST/$stamp ~/ResearchOps-VIST/current"
done
echo "Deployed immutable pack: $stamp"
