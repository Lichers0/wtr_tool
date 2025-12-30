# Git worktree manager shell wrapper (for auto-cd feature)
#
# Installation (add to ~/.zshrc or ~/.bashrc):
#   source /path/to/wtr/shell/wtr.sh
#   eval "$(command wtr --completion zsh)"  # or bash
#
# This overrides 'wtr' command with auto-cd wrapper.

wtr() {
    command wtr "$@"
    local exit_code=$?

    local cd_file="/tmp/.wtr_cd_$USER"
    if [[ -f "$cd_file" ]]; then
        local target
        target="$(cat "$cd_file")"
        rm -f "$cd_file"
        if [[ -d "$target" ]]; then
            cd "$target" && echo "Switched to: $target"
        fi
    fi

    return $exit_code
}
