#!/usr/bin/env bash
# N5: an unannotated dynamic construct in scanned scope
set -euo pipefail
printf '#!/usr/bin/env bash\neval "$X"\n' > scripts/ai/corpus-canary.sh
