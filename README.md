# WTR - Git Worktree Manager

CLI/TUI utility for managing git worktrees with ease.

## Features

- **TUI mode** — interactive interface with fuzzy search
- **CLI mode** — scriptable commands for automation
- **Auto-cd** — automatically change directory after creating/switching worktrees
- **Shell integration** — completions for bash, zsh, fish
- **Fuzzy search** — quickly find branches by partial name
- **Bulk operations** — delete multiple worktrees at once
- **Smart defaults** — auto-detect main branch, sensible prune behavior

## Quick Install

```bash
curl -sSL https://raw.githubusercontent.com/Lichers0/wtr_tool/master/install.sh | bash
```

Or with wget:
```bash
wget -qO- https://raw.githubusercontent.com/Lichers0/wtr_tool/master/install.sh | bash
```

### Manual Installation

```bash
# Clone repository
git clone https://github.com/Lichers0/wtr_tool.git
cd wtr_tool

# Install Python package
pip install -e .

# Add shell integration (bash/zsh)
echo 'source /path/to/wtr_tool/shell/wtr.sh' >> ~/.bashrc

# Or for fish
echo 'source /path/to/wtr_tool/shell/wtr.fish' >> ~/.config/fish/config.fish
```

## Usage

### TUI Mode (default)
```bash
wtr
```

### CLI Commands
```bash
# List worktrees
wtr list
wtr ls

# Create worktree
wtr add <branch>           # from existing branch
wtr add -b <branch>        # create new branch
wtr add -b <branch> <base> # create from specific base

# Delete worktree
wtr delete <branch>
wtr rm <branch>

# Prune stale worktrees
wtr prune

# Generate shell completions
wtr completion bash
wtr completion zsh
wtr completion fish
```

## Configuration

Create `~/.config/wtr/config.toml` or `.wtrrc` in repository root:

```toml
[defaults]
base = "main"  # default base branch for new worktrees

[ui]
show_status = true
color = true

[prune]
auto = false
```

## Requirements

- Python 3.10+
- Git 2.17+

## License

MIT
