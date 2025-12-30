# WTR shell wrapper for Fish
# Enables auto-cd after worktree operations

function wtr --description "Git Worktree Manager"
    # Create temp file for cd request
    set -l cd_file (mktemp)

    # Run wtr with cd-file argument
    command wtr --cd-file="$cd_file" $argv
    set -l exit_code $status

    # Check if we need to cd
    if test -s "$cd_file"
        set -l target_dir (cat "$cd_file")
        if test -d "$target_dir"
            cd "$target_dir"
        end
    end

    # Cleanup
    rm -f "$cd_file"

    return $exit_code
end
