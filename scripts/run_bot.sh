#!/usr/bin/env bash
# Тримає bot.py живим до дедлайну BOT_MAX_SECONDS: якщо процес падає —
# перезапускає з наростаючою паузою. Нормальний вихід за дедлайном = код 0.
# Код 2 від bot.py = помилка конфігурації (немає токенів) -> не перезапускаємо.
set -u

MAX_SECONDS="${BOT_MAX_SECONDS:-20700}"
start=$(date +%s)
backoff=5
stop=0
pid=""

on_signal() {
  stop=1
  [ -n "$pid" ] && kill -TERM "$pid" 2>/dev/null
}
trap on_signal INT TERM

while :; do
  remaining=$(( MAX_SECONDS - ( $(date +%s) - start ) ))
  if [ "$remaining" -le 30 ]; then
    echo "[run_bot] deadline reached, handing over"
    exit 0
  fi

  echo "[run_bot] starting bot.py (time left: ${remaining}s)"
  run_start=$(date +%s)
  timeout --signal=TERM --kill-after=20 "$remaining" python -u bot.py &
  pid=$!
  wait "$pid"
  code=$?
  # wait міг бути перерваний сигналом -> дочекатися коректного завершення бота
  if [ "$stop" -eq 1 ]; then
    wait "$pid" 2>/dev/null
    echo "[run_bot] stopped by signal"
    exit 0
  fi
  pid=""

  if [ "$code" -eq 124 ]; then
    echo "[run_bot] deadline reached, handing over"
    exit 0
  fi
  if [ "$code" -eq 2 ]; then
    echo "[run_bot] configuration error (exit 2) - not restarting" >&2
    exit 1
  fi

  ran=$(( $(date +%s) - run_start ))
  echo "[run_bot] bot.py exited with code ${code} after ${ran}s" >&2
  if [ "$ran" -ge 300 ]; then
    backoff=5
  else
    backoff=$(( backoff * 2 > 120 ? 120 : backoff * 2 ))
  fi
  echo "[run_bot] restarting in ${backoff}s"
  sleep "$backoff" &
  wait $!
  [ "$stop" -eq 1 ] && exit 0
done
