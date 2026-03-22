#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper for chat-completions mode.
# Example:
#   OPENAI_BASE_URL=http://10.67.116.243:3001/v1 OPENAI_API_KEY=... \
#   ./fc_runloop.sh runloop_agent/example.mcp.toml IKT-Qwen3-Coder-30B-A3B-Instruct PKT-20231

CONFIG=${1:?config toml}
MODEL=${2:?model}
JIRA_KEY=${3:-}

export LOG_LEVEL=${LOG_LEVEL:-INFO}

cd "$(dirname "$0")"

if [[ -n "$JIRA_KEY" ]]; then
  python3 fc_runloop.py --config "$CONFIG" --model "$MODEL" --jira-key "$JIRA_KEY" --log-level "$LOG_LEVEL"
else
  python3 fc_runloop.py --config "$CONFIG" --model "$MODEL" --log-level "$LOG_LEVEL"
fi
