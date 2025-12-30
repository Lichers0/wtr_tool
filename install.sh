#!/bin/bash
set -e

# ========== CONSTANTS ==========
REPO_URL="https://github.com/Lichers0/wtr_tool.git"
INSTALL_DIR="$HOME/.local/share/wtr"
BIN_DIR="$HOME/.local/bin"

# ========== FUNCTIONS ==========

# Detect current shell
detect_shell() {
    if [ -n "$FISH_VERSION" ]; then
        echo "fish"
    elif [ -n "$ZSH_VERSION" ]; then
        echo "zsh"
    elif [ -n "$BASH_VERSION" ]; then
        echo "bash"
    else
        # Fallback: check $SHELL
        case "$SHELL" in
            */fish) echo "fish" ;;
            */zsh)  echo "zsh" ;;
            *)      echo "bash" ;;
        esac
    fi
}

# Get RC file for shell
get_rc_file() {
    case "$1" in
        fish) echo "$HOME/.config/fish/config.fish" ;;
        zsh)  echo "$HOME/.zshrc" ;;
        bash)
            if [ -f "$HOME/.bash_profile" ]; then
                echo "$HOME/.bash_profile"
            else
                echo "$HOME/.bashrc"
            fi
            ;;
    esac
}

# Get completions directory
get_completion_dir() {
    case "$1" in
        fish) echo "$HOME/.config/fish/completions" ;;
        zsh)  echo "$HOME/.zsh/completions" ;;
        bash) echo "$HOME/.local/share/bash-completion/completions" ;;
    esac
}

# Check dependencies
check_dependencies() {
    echo "Checking dependencies..."

    if ! command -v git &> /dev/null; then
        echo "Error: git is not installed"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        echo "Error: python3 is not installed"
        exit 1
    fi

    if ! command -v pip3 &> /dev/null && ! python3 -m pip --version &> /dev/null; then
        echo "Error: pip is not installed"
        exit 1
    fi
}

# Install wtr
install_wtr() {
    echo "Installing wtr..."

    # Clone repository
    if [ -d "$INSTALL_DIR" ]; then
        echo "Updating existing installation..."
        cd "$INSTALL_DIR"
        git pull origin master
    else
        echo "Cloning repository..."
        git clone "$REPO_URL" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi

    # Install Python package
    echo "Installing Python package..."
    python3 -m pip install --user -e . --quiet

    # Create bin directory if not exists
    mkdir -p "$BIN_DIR"
}

# Setup shell integration
setup_shell_integration() {
    local shell_type="$1"
    local rc_file=$(get_rc_file "$shell_type")
    local completion_dir=$(get_completion_dir "$shell_type")

    echo "Setting up $shell_type integration..."

    # Create completions directory
    mkdir -p "$completion_dir"

    # Copy completion file
    case "$shell_type" in
        fish)
            cp "$INSTALL_DIR/shell/completions/wtr.fish" "$completion_dir/"
            ;;
        zsh)
            cp "$INSTALL_DIR/shell/completions/wtr.zsh" "$completion_dir/_wtr"
            ;;
        bash)
            cp "$INSTALL_DIR/shell/completions/wtr.bash" "$completion_dir/wtr"
            ;;
    esac

    # Add source shell wrapper to RC file
    local source_line
    case "$shell_type" in
        fish)
            source_line="source $INSTALL_DIR/shell/wtr.fish"
            ;;
        *)
            source_line="source $INSTALL_DIR/shell/wtr.sh"
            ;;
    esac

    # Check if line already exists
    if ! grep -qF "$source_line" "$rc_file" 2>/dev/null; then
        echo "" >> "$rc_file"
        echo "# WTR - Git Worktree Manager" >> "$rc_file"
        echo "$source_line" >> "$rc_file"
        echo "Added wtr integration to $rc_file"
    else
        echo "wtr integration already present in $rc_file"
    fi

    # For zsh: add completions path to fpath
    if [ "$shell_type" = "zsh" ]; then
        local fpath_line="fpath=($completion_dir \$fpath)"
        if ! grep -qF "fpath=($completion_dir" "$rc_file" 2>/dev/null; then
            # Insert before autoload if exists, otherwise after WTR comment
            if grep -q "autoload -Uz compinit" "$rc_file"; then
                sed -i.bak "/autoload -Uz compinit/i\\
$fpath_line" "$rc_file" && rm -f "$rc_file.bak"
            else
                echo "$fpath_line" >> "$rc_file"
                echo "autoload -Uz compinit && compinit" >> "$rc_file"
            fi
        fi
    fi
}

# ========== MAIN ==========

main() {
    echo "================================"
    echo "  WTR Installer"
    echo "  Git Worktree Manager"
    echo "================================"
    echo ""

    check_dependencies

    local shell_type=$(detect_shell)
    echo "Detected shell: $shell_type"

    install_wtr
    setup_shell_integration "$shell_type"

    echo ""
    echo "================================"
    echo "  Installation complete!"
    echo "================================"
    echo ""
    echo "Restart your shell or run:"
    case "$shell_type" in
        fish) echo "  source ~/.config/fish/config.fish" ;;
        zsh)  echo "  source ~/.zshrc" ;;
        bash) echo "  source ~/.bashrc" ;;
    esac
    echo ""
    echo "Then try: wtr --help"
}

main "$@"
