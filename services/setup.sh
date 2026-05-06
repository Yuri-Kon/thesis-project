#!/usr/bin/env bash
set -euo pipefail
export TERM=xterm-256color

# 基本路径
WORKDIR="/root/projects/2022112879/remote-model-rest"
PLM_PYTHON="/root/autodl-tmp/envs/plm/bin/python"
LOG_DIR="/root/autodl-tmp/logs/remote-model-rest"
mkdir -p "$LOG_DIR"

# ProtGPT2 REST
PROTGPT2_SESSION="protgpt2_rest"
PROTGPT2_PORT="8100"
PROTGPT2_BASE_DIR="/root/autodl-tmp/remote/plm_jobs"
PROTGPT2_MODEL_DIR="/root/autodl-tmp/models/plm/ProtGPT2"
PROTGPT2_LOG="$LOG_DIR/protgpt2_rest.log"

# OpenFold3 REST
OF3_SESSION="openfold3_rest"
OF3_PORT="8200"
OF3_BASE_DIR="/root/autodl-tmp/remote/openfold3_jobs"
OF3_MODEL_DIR="/root/autodl-tmp/models/openfold3"
OF3_PREDICT_BIN="run_openfold"
OF3_DEVICE="cuda"
OF3_RUNNER_YAML="/root/projects/2022112879/remote-model-rest/services/openfold3_rest_server/config/openfold3_no_deepspeed_evo_attention.yml"
OF3_LOG="$LOG_DIR/openfold3_rest.log"

start_tmux_session() {
  local session_name="$1"
  local command="$2"
  local log_file="$3"

  if tmux has-session -t "$session_name" 2>/dev/null; then
    echo "[skip] tmux session already exists: $session_name"
  else
    tmux new-session -d -s "$session_name" bash -lc "$command"
    echo "[ok] requested tmux session: $session_name"
  fi

  sleep 1
  if tmux has-session -t "$session_name" 2>/dev/null; then
    local pane_pid
    pane_pid="$(tmux list-panes -t "$session_name" -F '#{pane_pid}' | head -n 1 || true)"
    echo "[alive] tmux session still running: $session_name"
    tmux list-panes -t "$session_name" -F '[pane] #{pane_pid} #{pane_current_command}'
    if [ -n "$pane_pid" ] && ps -p "$pane_pid" -o pid=,ppid=,cmd=; then
      :
    fi
    return 0
  fi

  echo "[dead] tmux session exited immediately: $session_name"
  if [ -f "$log_file" ]; then
    echo "--- last 80 lines of $log_file ---"
    tail -n 80 "$log_file"
    echo "--- end log ---"
  else
    echo "[warn] log file not found: $log_file"
  fi
  return 1
}

PROTGPT2_CMD="cd \"$WORKDIR\" && \
export PLM_REST_BASE_DIR=\"$PROTGPT2_BASE_DIR\" && \
export PLM_MODEL_DIR=\"$PROTGPT2_MODEL_DIR\" && \
exec \"$PLM_PYTHON\" -m uvicorn services.plm_rest_server.app:app --host 0.0.0.0 --port $PROTGPT2_PORT >> \"$PROTGPT2_LOG\" 2>&1"

OF3_CMD="cd \"$WORKDIR\" && \
export OPENFOLD3_REST_BASE_DIR=\"$OF3_BASE_DIR\" && \
export OPENFOLD3_MODEL_DIR=\"$OF3_MODEL_DIR\" && \
export OPENFOLD3_PREDICT_BIN=\"$OF3_PREDICT_BIN\" && \
export OPENFOLD3_DEVICE=\"$OF3_DEVICE\" && \
export OPENFOLD3_RUNNER_YAML=\"$OF3_RUNNER_YAML\" && \
exec \"$PLM_PYTHON\" -m uvicorn services.openfold3_rest_server.app:app --host 0.0.0.0 --port $OF3_PORT >> \"$OF3_LOG\" 2>&1"

# 启动 ProtGPT2 服务
start_tmux_session "$PROTGPT2_SESSION" "$PROTGPT2_CMD" "$PROTGPT2_LOG"

# 启动 OpenFold3 服务
start_tmux_session "$OF3_SESSION" "$OF3_CMD" "$OF3_LOG"

echo "All Done"
echo "ProtGPT2 log: $PROTGPT2_LOG"
echo "OpenFold3 log: $OF3_LOG"
echo "ProtGPT2: tmux attach -t $PROTGPT2_SESSION"
echo "OpenFold3: tmux attach -t $OF3_SESSION"
