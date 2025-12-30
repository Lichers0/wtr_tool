_wtr() {
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="-l --list -d --delete --prune --completion add"

    # Handle 'add' subcommand
    if [[ "${COMP_WORDS[1]}" == "add" ]]; then
        case "${prev}" in
            -b|--base)
                local branches=$(git branch --format='%(refname:short)' 2>/dev/null)
                COMPREPLY=( $(compgen -W "${branches}" -- ${cur}) )
                return 0
                ;;
            -c|--commit)
                local tags=$(git tag 2>/dev/null)
                COMPREPLY=( $(compgen -W "${tags}" -- ${cur}) )
                return 0
                ;;
        esac
        if [[ ${cur} == -* ]]; then
            COMPREPLY=( $(compgen -W "-b --base -c --commit -B --new-branch" -- ${cur}) )
        fi
        return 0
    fi

    case "${prev}" in
        -d|--delete)
            local worktrees=$(wtr --list 2>/dev/null | cut -f1)
            COMPREPLY=( $(compgen -W "${worktrees}" -- ${cur}) )
            return 0
            ;;
        --completion)
            COMPREPLY=( $(compgen -W "zsh bash fish" -- ${cur}) )
            return 0
            ;;
    esac

    if [[ ${cur} == -* ]]; then
        COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
    else
        local worktrees=$(wtr --list 2>/dev/null | cut -f1)
        COMPREPLY=( $(compgen -W "add ${worktrees}" -- ${cur}) )
    fi
}
complete -F _wtr wtr
