#compdef wtr

_wtr() {
    local -a branches worktrees tags

    # Get existing worktrees
    worktrees=($(command wtr --list 2>/dev/null | cut -f1))

    # Get local branches
    branches=($(git branch --format='%(refname:short)' 2>/dev/null))

    # Get tags
    tags=($(git tag 2>/dev/null))

    # Handle subcommands
    if [[ "${words[2]}" == "add" ]]; then
        _arguments \
            '1:name:' \
            '(-b --base)'{-b,--base}'[Base branch]:branch:($branches)' \
            '(-c --commit)'{-c,--commit}'[Commit or tag]:commit:($tags)' \
            '(-B --new-branch)'{-B,--new-branch}'[Create branch from commit]'
        return
    fi

    _arguments -C \
        '(-l --list)'{-l,--list}'[List existing worktrees]' \
        '(-d --delete)'{-d,--delete}'[Delete worktree]:branch:($worktrees)' \
        '--prune[Remove stale worktrees]' \
        '--completion[Generate shell completion]:shell:(zsh bash fish)' \
        '1:worktree or command:(add $worktrees)'
}

compdef _wtr wtr
