# Git worktree manager wrapper (for auto-cd feature)
function wtr --wraps='command wtr'
    command wtr $argv
    set -l exit_code $status

    set -l cd_file "/tmp/.wtr_cd_$USER"
    if test -f "$cd_file"
        set -l target (cat "$cd_file")
        rm -f "$cd_file"
        if test -d "$target"
            cd "$target" && echo "Switched to: $target"
        end
    end

    return $exit_code
end

function __fish_wtr_branches
    git branch --format='%(refname:short)' 2>/dev/null
end

function __fish_wtr_worktrees
    wtr --list 2>/dev/null | cut -f1
end

function __fish_wtr_tags
    git tag 2>/dev/null
end

complete -c wtr -f
complete -c wtr -s l -l list -d 'List existing worktrees'
complete -c wtr -s d -l delete -d 'Delete worktree' -xa '(__fish_wtr_worktrees)'
complete -c wtr -l prune -d 'Remove stale worktrees'
complete -c wtr -l completion -d 'Generate completion' -xa 'zsh bash fish'
complete -c wtr -n '__fish_is_first_arg' -a 'add' -d 'Create new worktree'
complete -c wtr -n '__fish_is_first_arg' -xa '(__fish_wtr_worktrees)'
complete -c wtr -n '__fish_seen_subcommand_from add' -s b -l base -d 'Base branch' -xa '(__fish_wtr_branches)'
complete -c wtr -n '__fish_seen_subcommand_from add' -s c -l commit -d 'Commit or tag' -xa '(__fish_wtr_tags)'
complete -c wtr -n '__fish_seen_subcommand_from add' -s B -l new-branch -d 'Create branch from commit'
