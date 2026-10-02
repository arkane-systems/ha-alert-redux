#!/usr/bin/env bash
# Run the test suite against an older Home Assistant, apart from CI.
#
# Usage: scripts/test-against-ha.sh <pytest-homeassistant-custom-component version> [pytest args]
#
# Each release of pytest-homeassistant-custom-component pins one HA release:
# 0.13.340 is HA 2026.6.4 (the minimum, hacs.json), 0.13.357 is HA 2026.8.3
# (the first with the llm tools platform). The venv (.venvs/<version>) gets the
# Python that HA release needs, every package as it was when the plugin was
# released (so later releases of HA's dependencies don't break it), and the
# requirements of HA's voice components, which the voice tests set up.
set -euo pipefail
PLUGIN=$1
shift
cd "$(dirname "$0")/.."
VENV=.venvs/$PLUGIN
PYPI=https://pypi.org/pypi

if [ ! -x "$VENV/bin/python" ]; then
  HA=$(curl -s "$PYPI/pytest-homeassistant-custom-component/$PLUGIN/json" | python3 -c \
    "import json,sys; print([r for r in json.load(sys.stdin)['info']['requires_dist'] if r.startswith('homeassistant')][0].split('==')[1])")
  PY=$(curl -s "$PYPI/homeassistant/$HA/json" | python3 -c \
    "import json,sys,re; print(re.search(r'3\.\d+', json.load(sys.stdin)['info']['requires_python']).group(0))")
  WHEN=$(curl -s "$PYPI/pytest-homeassistant-custom-component/$PLUGIN/json" | python3 -c \
    "import json,sys; print(max(u['upload_time_iso_8601'] for u in json.load(sys.stdin)['urls']))")
  echo "HA $HA on Python $PY, with packages as of $WHEN"
  uv venv -q "$VENV" --python "$PY"
  uv pip install -q -p "$VENV" --exclude-newer "$WHEN" \
    "pytest-homeassistant-custom-component==$PLUGIN"
  HA_DIR=$("$VENV/bin/python" -c "import homeassistant,os; print(os.path.dirname(homeassistant.__file__))")
  REQS=$(python3 - "$HA_DIR" <<'PY'
import json, sys
reqs = set()
for comp in ("conversation", "assist_pipeline", "tts", "ffmpeg", "stt", "wake_word"):
    try:
        with open(f"{sys.argv[1]}/components/{comp}/manifest.json") as manifest:
            reqs.update(json.load(manifest).get("requirements", []))
    except FileNotFoundError:
        pass
print(" ".join(sorted(reqs)))
PY
)
  uv pip install -q -p "$VENV" --exclude-newer "$WHEN" $REQS
fi
exec "$VENV/bin/python" -m pytest -p no:cacheprovider "$@"
