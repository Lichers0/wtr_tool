# wtr — Git Worktree Manager

## Overview

CLI-утилита с TUI-интерфейсом для управления git worktrees. Упрощает создание, переключение и удаление worktrees.

## Features

### Core
- TUI-интерфейс для выбора/создания веток
- Быстрое создание worktree через CLI-аргумент
- Удаление worktrees (без удаления веток)
- **Worktree от коммита/тега** — detached HEAD или новая ветка от коммита
- **Автоматическая реструктуризация** — преобразование репо в worktree-структуру

### Extended
- **Fuzzy search** — фильтрация веток:
  - Подстрока: `325` → `ENS-325` (score: 100)
  - Подпоследовательность: `ES5` → `ENS-325` (score: 95)
  - Fuzzy matching для опечаток (score: <95)
- **Статус worktree** — индикаторы состояния для каждой ветки:
  - `*` — dirty (незакоммиченные изменения)
  - `[+N]` — количество untracked файлов
  - `↑N ↓M` — ahead/behind remote
  - `Nd` — давность последнего коммита
  - `[S]` — есть stash
  - `[R]`/`[M]` — в процессе rebase/merge
- **Автоочистка** — удаление worktrees для merged/deleted веток (CLI + TUI)
- **Конфиг файл** — `.wtrrc` (TOML) для настроек
- **Shell completions** — автодополнение для zsh/bash/fish
- **Групповые операции** — выбор нескольких worktrees для удаления
- **Превью веток** — последние коммиты при навигации

## Directory Structure

```
<container>/                     # контейнер (не git repo)
├── master/                      # основная ветка (main/master)
│   ├── .git/                    # полноценная git директория
│   └── src/
├── feature-x/                   # worktree (рядом с основной веткой)
│   ├── .git                     # файл-ссылка на основной repo
│   └── src/
├── abc1234/                     # detached HEAD worktree
│   ├── .git                     # файл-ссылка
│   └── src/
└── feature-y/                   # worktree
    ├── .git
    └── src/
```

### Определение основной ветки

Основная ветка определяется в следующем порядке:
1. `git symbolic-ref refs/remotes/origin/HEAD` — из настроек remote
2. Наличие ветки `main` или `master`
3. Текущая ветка (fallback)

### Автоматическая реструктуризация

При запуске `wtr` проверяется структура репозитория. Если:
- Текущая папка не соответствует названию главной ветки
- И это не worktree (`.git` — директория, не файл)

То предлагается реструктуризация:

```
Repository is not in worktree structure.
Move 'master' to worktree structure? [y/N]
```

**При подтверждении:**
```
/myproject/          →    /myproject/
  .git/                     master/
  src/                        .git/
                              src/
```

**При отказе:** worktree-операции блокируются.

## Project Structure

```
wtr/
├── pyproject.toml
├── wtr_spec.md
├── shell/
│   ├── wtr.sh                 # shell-обёртка для cd
│   └── completions/
│       ├── wtr.zsh            # zsh completion
│       ├── wtr.bash           # bash completion
│       └── wtr.fish           # fish completion
└── src/wtr/
    ├── __init__.py
    ├── cli.py                 # CLI entry point, argument parsing
    ├── config.py              # Config file loading
    ├── git.py                 # GitWorktreeManager class
    ├── fuzzy.py               # Fuzzy search helpers
    └── tui.py                 # TUI application (textual)
```

## CLI Interface

```bash
wtr                            # launch TUI
wtr <branch>                   # switch to existing worktree (no TUI)
wtr add <name>                 # create worktree for branch
wtr add <name> -b <branch>     # create worktree from base branch
wtr add -c <commit>            # detached HEAD at commit/tag
wtr add <name> -c <commit>     # detached HEAD with custom dir name
wtr add <name> -c <commit> -B  # new branch from commit
wtr -l, --list                 # list existing worktrees
wtr -d, --delete <branch>      # delete worktree
wtr --prune                    # remove worktrees for merged/deleted branches
wtr --completion <shell>       # generate shell completion (zsh/bash/fish)
```

## Exit Codes

| Code | Meaning                              | Shell Action |
|------|--------------------------------------|--------------|
| 0    | Success, stdout contains path       | cd to path   |
| 1    | No action (cancel, list, info)      | print stdout |
| 2    | Error                                | print stderr |

## Shell Integration

`wtr` работает как standalone команда после `pip install`.

**Для auto-cd (опционально):**
```bash
# ~/.zshrc — однострочная функция
wtr() { local p=$(command wtr "$@"); [[ -d "$p" ]] && cd "$p" || echo "$p"; }

# Или source обёртки
source /path/to/wtr/shell/wtr.sh  # создаёт функцию wtrc
```

**Shell completions:**
```bash
eval "$(wtr --completion zsh)"   # zsh
eval "$(wtr --completion bash)"  # bash
```

## TUI Flow

### Main Screen
```
┌──────────────────────────────────────────────────────────┐
│  Git Worktree Manager                                    │
├──────────────────────────────────────────────────────────┤
│  Filter: [feat_______________]                           │
│                                                          │
│  Branches:                                               │
│  ┌────────────────────────────────────────────────────┐  │
│  │ 📁 ● main                           ↑1        2h   │  │
│  │ 📁   feature-auth    * [+2]         ↓3        1d   │  │
│  │      feature-api                [S]           5d   │  │
│  │ 📁   feature-db                               3d   │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Preview:                                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │ abc1234 Fix auth flow (2 days ago)                 │  │
│  │ def5678 Add login endpoint (3 days ago)            │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  [Enter] select  [Space] multi  [d] delete  [p] prune    │
│  [q] quit                                                │
└──────────────────────────────────────────────────────────┘
```

### Статус индикаторы
- `📁` — есть worktree (пусто если нет)
- `●` — текущая ветка
- `*` — dirty (есть изменения)
- `[+N]` — untracked файлов
- `↑N ↓M` — ahead/behind remote
- `Nd/Nh` — время последнего коммита
- `[S]` — есть stash
- `[R]` — rebase in progress
- `[M]` — merge in progress

### Enter Behavior

Поведение Enter зависит от фокуса:

**Фокус на поле фильтра:**
- Создаёт новую ветку + worktree
- Имя ветки = текст из поля фильтра
- Базовая ветка по умолчанию = ветка при запуске wtr

**Фокус на списке веток:**
- Worktree существует → "Переключиться?" (Yes/No)
  - Yes → обновить симлинк `wt` и перейти
  - No → закрыть диалог
- Worktree не существует → создать worktree для выбранной ветки

**Первый элемент списка всегда выделен.**

### Dialogs

**Switch confirmation (existing worktree):**
```
Switch to feature-auth?
[Yes] [No]
```

**Create worktree:**
```
┌─────────────────────────────────────────┐
│  Create worktree                        │
├─────────────────────────────────────────┤
│  Name: feature-api                      │
│                                         │
│  Mode: [Branch] [Commit] [Tag]          │
│                                         │
│  Base branch: [main___________]         │
│  ┌────────────────────────────┐         │
│  │   main                     │         │
│  │   develop                  │         │
│  └────────────────────────────┘         │
│                                         │
│  [Create] [Cancel]                      │
└─────────────────────────────────────────┘
```

**Mode=Commit/Tag (detached HEAD):**
```
│  Commit SHA: [abc1234________]          │
│  ☐ Create new branch                    │
```
- Переключатель режима: Branch / Commit / Tag
- Fuzzy-фильтрация для веток и тегов
- Чекбокс "Create new branch" для создания ветки от коммита

**Uncommitted warning (before create):**
```
⚠ Uncommitted changes in base branch
Branch: feature-x
Modified files:
• src/main.py
• src/utils.py
• tests/test_main.py
[Continue anyway] [Cancel]
```
- Показывается если в worktree базовой ветки есть незакоммиченные файлы
- Максимум 10 файлов, остальные скрыты ("... and N more")

**After creation:**
```
Go to feature-api?
[Yes] [No]
```

**Prune dialog (in TUI):**
```
Found 3 stale worktrees:
☑ old-feature     (branch deleted)
☑ merged-fix      (merged to main)
☐ wip-experiment  (branch deleted)
[Delete selected] [Cancel]
```

**Multi-delete:**
```
Delete 2 worktrees?
- feature-old
- feature-test
[Delete] [Cancel]
```

## Modules

### git.py — GitWorktreeManager

```python
@dataclass
class BranchStatus:
    dirty: bool                    # uncommitted changes
    untracked_count: int           # untracked files
    ahead: int                     # commits ahead of remote
    behind: int                    # commits behind remote
    last_commit_time: datetime     # last commit timestamp
    has_stash: bool                # has stash entries
    rebase_in_progress: bool       # rebase in progress
    merge_in_progress: bool        # merge in progress

class GitWorktreeManager:
    # Properties
    root: Path                     # path to current repo/worktree
    container: Path                # parent directory (worktrees live here)

    def __init__(path: Path | None = None)
    def get_main_branch() -> str               # from origin/HEAD or fallback main/master
    def get_main_repo_path() -> Path           # container/<main_branch>
    def is_valid_structure() -> bool           # check if folder matches branch
    def needs_restructure() -> bool            # check if restructure needed
    def restructure_to_worktree() -> Path      # perform restructure, return new root
    def list_local_branches() -> list[str]
    def list_tags() -> list[str]               # list all tags
    def list_worktrees() -> dict[str, Path]    # worktrees in container
    def branch_exists(name: str) -> bool
    def worktree_exists(branch: str) -> bool
    def get_worktree_path(branch: str) -> Path # returns container/branch
    def resolve_commit(commit_ish: str) -> str | None  # resolve to SHA or None
    def create_worktree(
        name: str,
        base_branch: str | None = None,
        commit: str | None = None,
        create_branch: bool = False,
    ) -> Path
    def delete_worktree(branch: str) -> None
    def get_current_branch() -> str | None

    # Extended methods
    def get_branch_status(branch: str) -> BranchStatus
    def get_recent_commits(branch: str, count: int = 5) -> list[tuple[str, str, datetime]]
    def find_stale_worktrees() -> list[tuple[str, str]]  # [(branch, reason), ...]
    def is_branch_merged(branch: str, into: str = "main") -> bool
    def prune_worktrees(branches: list[str]) -> None
    def get_uncommitted_files(branch: str) -> list[str]  # modified/staged/untracked files
```

### tui.py — TUI Components

- `WorktreeApp` — main application
  - `base_branch` — branch where app was launched (default for new worktrees)
  - `tags` — list of tags for CreateWorktreeDialog
- `BranchItem` — list item with status indicators
- `BranchPreview` — commit preview panel
- `ConfirmDialog` — yes/no modal
- `CreateWorktreeResult` — dataclass for dialog result (name, base_branch, commit, create_branch)
- `CreateWorktreeDialog` — create worktree modal with mode selection (Branch/Commit/Tag)
- `UncommittedWarningDialog` — warning about uncommitted files in base branch
- `PruneDialog` — select stale worktrees modal
- `MultiDeleteDialog` — confirm multi-delete modal

### cli.py — Entry Point

- Argument parsing (argparse)
- Route to TUI or quick commands
- Handle exit codes

### fuzzy.py — Fuzzy Search

```python
def is_subsequence(query: str, text: str) -> bool
    """Check if query chars appear in text in order (e.g. 'ES5' in 'ENS-325')."""

def fuzzy_filter(items: list[str], query: str, threshold: int = 95) -> list[tuple[str, int]]
    """
    Filter items by matching against query. Returns (item, score) sorted by score.
    Scoring:
    - 100: exact substring match
    - 95: subsequence match
    - <95: fuzzy match (thefuzz library)
    """

def fuzzy_match(items: list[str], query: str, threshold: int = 95) -> list[str]
    """Convenience wrapper, returns only item names."""
```

## Config File

`.wtrrc` в корне репозитория или `~/.config/wtr/config.toml`:

```toml
[worktree]
default_base = ""           # empty = auto-detect (main or master)

[ui]
show_status = true          # show status indicators
show_preview = true         # show commit preview
preview_count = 5           # number of commits in preview

[prune]
auto_suggest = true         # suggest prune on TUI start if stale found
```

## Dependencies

```toml
[project]
dependencies = [
    "textual>=0.40.0",
    "GitPython>=3.1.0",
    "thefuzz>=0.22.0",      # fuzzy matching
    "tomli>=2.0.0",         # config parsing (Python < 3.11)
]
```

## Installation

```bash
pip install -e /path/to/wtr
```

**Опционально (auto-cd):**
```bash
# Добавить в ~/.zshrc
wtr() { local p=$(command wtr "$@"); [[ -d "$p" ]] && cd "$p" || echo "$p"; }
eval "$(wtr --completion zsh)"
```
