#!/usr/bin/env bash
# =============================================================================
# agent_bootstrap.sh — холодный старт агента по протоколу AGENT.md
#
# Реализует фазы 0–3 (состояние, окружение, PTY, git) и печатает Markdown-отчёт
# восстановления (фаза 4). Секреты НИКОГДА не печатает: весь вывод проходит
# через redact() — токены маскируются как ghp_****.
#
# Использование:
#   ./scripts/agent_bootstrap.sh                # авто-поиск репо в ~/my-project
#   ./scripts/agent_bootstrap.sh /путь/к/репо   # явно указанные репозитории
#   ./scripts/agent_bootstrap.sh --save [пути]  # отчёт также в .agent/bootstrap-report.md
#
# Выход: код 0 всегда (отчёт важнее отдельных сбоев фаз).
# =============================================================================
set -uo pipefail

# --- --save: перезапустить себя с редиректом вывода в файл -------------------
if [ "${1:-}" = "--save" ]; then
  shift
  mkdir -p .agent 2>/dev/null
  exec bash "$0" "$@" > .agent/bootstrap-report.md
fi

# --- Гигиена: маскирование токенов во всём выводе ---------------------------
redact() {
  sed -E \
    -e 's/(ghp_|github_pat_|gho_|ghu_|ghs_)[A-Za-z0-9_-]{8,}/\1****/g' \
    -e 's/(glpat-|gtc_)[A-Za-z0-9_-]{8,}/\1****/g' \
    -e 's/(x-access-token|oauth2):[^@[:space:]]+@/\1:****@/g' \
    -e 's/(token|password|passwd|secret)["'"'"'= :]+[^"'"'"' ,]+/\1=****/Ig'
}

# --- Авто-поиск репозиториев --------------------------------------------------
discover_repos() {
  local roots=("/home/z/my-project" "$HOME")
  for root in "${roots[@]}"; do
    [ -d "$root" ] || continue
    local d
    for d in "$root"/* "$root"/*/; do
      [ -e "$d/.git" ] && printf '%s\n' "${d%/}"
    done
  done | sort -u
}

REPOS=()
if [ "$#" -gt 0 ]; then REPOS=("$@"); else REPOS=($(discover_repos)); fi

echo "# Отчёт восстановления — $(date -u '+%Y-%m-%d %H:%M UTC')"
echo

# =============================================================================
# ФАЗА 0 — состояние (AGENT_STATE.md)
# =============================================================================
echo "## Фаза 0 — Вектор движения (AGENT_STATE.md)"
echo
if [ "${#REPOS[@]}" -eq 0 ]; then echo "- репозитории не найдены"; fi
for repo in "${REPOS[@]}"; do
  name=$(basename "$repo")
  if [ -f "$repo/AGENT_STATE.md" ]; then
    echo "**$name:**"
    sed -n '1,25p' "$repo/AGENT_STATE.md" | redact
    echo
  else
    echo "- $name: AGENT_STATE.md отсутствует — восстановление по git log (§1 AGENT.md)"
  fi
done
echo

# =============================================================================
# ФАЗА 1 — рекогносцировка окружения
# =============================================================================
echo "## Фаза 1 — Окружение"
echo
echo "- host: $(hostname 2>/dev/null || echo '?'), $(uname -srm 2>/dev/null)"
echo "- диск: $(df -h /home 2>/dev/null | tail -1 | awk '{print $3" использовано, "$4" свободно ("$5")"}')"
LINE="- инструменты:"
for t in git cargo tmux gh glab python3; do
  if command -v "$t" >/dev/null 2>&1; then LINE="$LINE $t=ok"; else LINE="$LINE $t=НЕТ"; fi
done
echo "$LINE"
echo "  (НЕТ не блокирует: доустановить по §3.2 AGENT.md — tmux обязателен для §2)"
echo

# =============================================================================
# ФАЗА 2 — сканирование PTY и процессов
# =============================================================================
echo "## Фаза 2 — Фоновые задачи"
echo
if command -v tmux >/dev/null 2>&1; then
  SESSIONS=$(tmux ls -F '#{session_name}' 2>/dev/null || true)
  if [ -n "$SESSIONS" ]; then
    for s in $SESSIONS; do
      echo "- **tmux:$s** — последние строки:"
      tmux capture-pane -p -t "$s" -S -20 2>/dev/null | redact | grep -v '^[[:space:]]*$' | tail -8 | sed 's/^/      /'
      echo
    done
  else
    echo "- tmux установлен, активных сессий нет — длительных задач не было (или VM перезагружена)"
  fi
else
  echo "- tmux НЕ установлен: фоновых PTY-сессий быть не может. Поставить: apt-get install -y tmux (§3.2)"
fi
echo "- длительные процессы:"
ps ax -o pid,etime,cmd 2>/dev/null \
  | grep -E 'cargo|rustc|python3|node|qemu|poler' \
  | grep -vE 'grep|agent_bootstrap' | head -6 | sed 's/^/      /' | redact || true
echo

# =============================================================================
# ФАЗА 3 — git: fetch-before-work, расхождения local vs remote
# =============================================================================
echo "## Фаза 3 — Git (fetch-before-work)"
echo

# --- Автопроверка живости токена из файла-хранилища ---------------------------
TOKEN_FILE="/home/z/my-project/upload/гитхаб токен .txt"
if [ -f "$TOKEN_FILE" ] && command -v curl >/dev/null 2>&1; then
  TOK=$(tr -d '[:space:]' < "$TOKEN_FILE" 2>/dev/null || true)
  if [ -n "$TOK" ]; then
    CODE=$(curl -s -m 15 -o /dev/null -w "%{http_code}" \
      -H "Authorization: token $TOK" https://api.github.com/user)
    case "$CODE" in
      200) echo "- credentials: github-токен из файла-хранилища ВАЛИДЕН (API 200) — передавать повторно не нужно" ;;
      401) echo "- credentials: github-токен из файла-хранилища НЕВАЛИДЕН (API 401) — попросить новый PAT (scope: repo) у пользователя" ;;
      *)   echo "- credentials: github API недоступен (HTTP $CODE) — проверить позже" ;;
    esac
    unset TOK
  else
    echo "- credentials: файл-хранилище токена пуст — попросить пользователя передать PAT (scope: repo)"
  fi
else
  echo "- credentials: файл-хранилище токена не найден — попросить пользователя передать PAT (scope: repo)"
fi
echo
for repo in "${REPOS[@]}"; do
  name=$(basename "$repo")
  cd "$repo" 2>/dev/null || { echo "- $name: недоступен"; continue; }
  BRANCH=$(git branch --show-current 2>/dev/null || echo '?')
  echo "### $name @ $BRANCH"
  git status --short --branch 2>/dev/null | head -3 | redact
  if git remote get-url origin >/dev/null 2>&1; then
    timeout 25 git fetch origin --tags >/dev/null 2>&1 \
      && FETCH="ok" || FETCH="НЕДОСТУПЕН (сеть/credentials)"
    UP=$(git rev-parse --abbrev-ref @{upstream} 2>/dev/null || echo "origin/$BRANCH")
    if git rev-parse "$UP" >/dev/null 2>&1; then
      COUNTS=$(git rev-list --left-right --count "$UP...HEAD" 2>/dev/null || echo "? ?")
      BEHIND=$(echo "$COUNTS" | awk '{print $1}')
      AHEAD=$(echo "$COUNTS" | awk '{print $2}')
      STATE="SYNC"
      if [ "$AHEAD" != "0" ] && [ "$AHEAD" != "?" ]; then STATE="AHEAD $AHEAD — push после зелёных тестов"; fi
      if [ "$BEHIND" != "0" ] && [ "$BEHIND" != "?" ]; then STATE="BEHIND $BEHIND — git pull --rebase --autostash"; fi
      if [ "$AHEAD" != "0" ] && [ "$BEHIND" != "0" ] && [ "$AHEAD" != "?" ] && [ "$BEHIND" != "?" ]; then
        STATE="DIVERGED ($BEHIND/$AHEAD) — rebase, при конфликтах STOP (§5)"
      fi
      echo "- remote: fetch $FETCH, состояние: $STATE"
    else
      echo "- remote: fetch $FETCH, upstream-ссылка не найдена"
    fi
  else
    echo "- remote не настроен — репозиторий живёт только локально (риск потери, §3.3)"
  fi
  echo "- последние коммиты:"
  git log --oneline -3 2>/dev/null | redact | sed 's/^/      /'
  echo
done

# =============================================================================
# ФАЗА 4 — вход в работу
# =============================================================================
echo "## Фаза 4 — Действие"
echo
echo "- Вектор движения: current_task → next_task из AGENT_STATE.md (фаза 0)"
echo "- Продолжить задачу БЕЗ переспроса пользователя; исключение — blocked_on."
echo "- Долгие проверки запускать в tmux (§2), самому продолжать другую работу."
echo
echo "---"
echo "Сгенерировано scripts/agent_bootstrap.sh — протокол AGENT.md (Context-Free Resilience)."
exit 0
