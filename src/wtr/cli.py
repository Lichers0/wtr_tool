"""CLI entry point for worktree manager."""

import argparse
import os
import sys
from pathlib import Path

from .config import load_config
from .git import GitWorktreeManager
from .tui import run_tui


def request_cd(path: str | Path) -> None:
    """Request shell wrapper to cd to path after exit."""
    cd_file = f"/tmp/.wtr_cd_{os.environ.get('USER', 'unknown')}"
    with open(cd_file, "w") as f:
        f.write(str(path))


SHELL_COMPLETIONS = {
    "zsh": """\
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
        _arguments \\
            '1:name:' \\
            '(-b --base)'{-b,--base}'[Base branch]:branch:($branches)' \\
            '(-c --commit)'{-c,--commit}'[Commit or tag]:commit:($tags)' \\
            '(-B --new-branch)'{-B,--new-branch}'[Create branch from commit]'
        return
    fi

    _arguments -C \\
        '(-l --list)'{-l,--list}'[List existing worktrees]' \\
        '(-d --delete)'{-d,--delete}'[Delete worktree]:branch:($worktrees)' \\
        '--prune[Remove stale worktrees]' \\
        '--completion[Generate shell completion]:shell:(zsh bash fish)' \\
        '1:worktree or command:(add $worktrees)'
}

compdef _wtr wtr
""",
    "bash": """\
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
""",
    "fish": """\
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
""",
}


HELP_EPILOG = """\
TUI Keybindings:
  Enter      Select branch / confirm action
  Space      Toggle multi-select for bulk delete
  d          Delete worktree (single or selected)
  p          Prune stale worktrees
  q, Escape  Quit

Examples:
  wtr                       Launch TUI
  wtr feature-auth          Switch to existing worktree
  wtr add feature-new       Create new worktree
  wtr add -b develop fix    Create from 'develop' branch
  wtr add -c abc1234        Detached HEAD at commit
  wtr add -c v1.2.0         Detached HEAD at tag
  wtr add fix -c abc1234 -B Create branch 'fix' from commit
  wtr --prune               Remove merged/deleted worktrees
"""


def handle_add_command() -> int:
    """Handle 'wtr add' subcommand with separate parser."""
    parser = argparse.ArgumentParser(
        description="Create new worktree",
        prog="wtr add",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Directory name (and branch name if creating branch)",
    )
    parser.add_argument(
        "-b", "--base",
        metavar="BRANCH",
        help="Base branch for new worktree",
    )
    parser.add_argument(
        "-c", "--commit",
        metavar="COMMIT",
        help="Create worktree at commit/tag (detached HEAD by default)",
    )
    parser.add_argument(
        "-B", "--new-branch",
        action="store_true",
        dest="create_branch",
        help="Create new branch from commit (use with -c)",
    )

    args = parser.parse_args(sys.argv[2:])

    # Validate arguments
    if args.commit and args.base:
        print("Error: --commit and --base are mutually exclusive", file=sys.stderr)
        return 2

    if args.create_branch and not args.commit:
        print("Error: --new-branch requires --commit", file=sys.stderr)
        return 2

    # Determine target name
    if args.target:
        target = args.target
    elif args.commit:
        # Use short commit SHA or tag name as directory name
        target = args.commit[:7] if len(args.commit) >= 7 else args.commit
    else:
        print("Error: target name required (or use -c for commit)", file=sys.stderr)
        return 2

    try:
        manager = GitWorktreeManager()
        config = load_config(manager.root)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2

    if not manager.is_valid_structure():
        print("Repository is not in worktree structure", file=sys.stderr)
        return 2

    return handle_add(
        manager,
        target,
        args.base,
        config,
        commit=args.commit,
        create_branch=args.create_branch,
    )


def main() -> int:
    """Main entry point."""
    # Handle 'add' subcommand separately to avoid argparse conflicts
    if len(sys.argv) >= 2 and sys.argv[1] == "add":
        return handle_add_command()

    parser = argparse.ArgumentParser(
        description="Git worktree manager with TUI",
        prog="wtr",
        epilog=HELP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "branch",
        nargs="?",
        help="Switch to existing worktree (skips TUI)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        dest="list_worktrees",
        help="List existing worktrees",
    )
    parser.add_argument(
        "--delete", "-d",
        metavar="BRANCH",
        help="Delete worktree for branch",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Remove worktrees for merged/deleted branches",
    )
    parser.add_argument(
        "--completion",
        metavar="SHELL",
        choices=["zsh", "bash", "fish"],
        help="Generate shell completion script",
    )

    args = parser.parse_args()

    # Handle --completion (doesn't need git repo)
    if args.completion:
        print(SHELL_COMPLETIONS[args.completion])
        return 1  # Don't cd

    try:
        manager = GitWorktreeManager()
        config = load_config(manager.root)
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        return 2

    # Handle --list
    if args.list_worktrees:
        worktrees = manager.list_worktrees()
        if not worktrees:
            print("No worktrees found", file=sys.stderr)
            return 1
        for branch, path in sorted(worktrees.items()):
            print(f"{branch}\t{path}")
        return 1  # Don't cd

    # Handle --prune
    if args.prune:
        return handle_prune(manager)

    # Handle --delete
    if args.delete:
        try:
            manager.delete_worktree(args.delete)
            print(f"Deleted worktree: {args.delete}", file=sys.stderr)
            return 1  # Don't cd
        except RuntimeError as e:
            print(str(e), file=sys.stderr)
            return 2

    # Check structure before worktree operations
    if not manager.is_valid_structure():
        result = handle_restructure(manager)
        if result is not None:
            return result

    # Handle quick branch argument (switch only)
    if args.branch:
        return handle_quick_branch(manager, args.branch)

    # Run TUI
    result = run_tui(manager, config)
    if result:
        request_cd(result)
        return 0
    return 1


def handle_restructure(manager: GitWorktreeManager) -> int | None:
    """
    Handle repository restructuring prompt.

    Returns:
        None - if restructure succeeded, continue execution
        int - exit code if should stop execution
    """
    main_branch = manager.get_main_branch()

    print(
        f"Repository is not in worktree structure.\n"
        f"Move '{main_branch}' to worktree structure? [y/N] ",
        end="",
        file=sys.stderr,
    )

    try:
        response = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled", file=sys.stderr)
        return 1

    if response != "y":
        print(
            "Worktree operations require valid structure.",
            file=sys.stderr,
        )
        return 1

    # Perform restructure
    try:
        new_root = manager.restructure_to_worktree()
        print(
            f"Restructured: {new_root}",
            file=sys.stderr,
        )
        request_cd(new_root)
        return 0
    except Exception as e:
        print(f"Restructure failed: {e}", file=sys.stderr)
        return 2


def handle_quick_branch(
    manager: GitWorktreeManager,
    branch: str,
) -> int:
    """Switch to existing worktree (no create)."""
    worktrees = manager.list_worktrees()

    if branch in worktrees:
        request_cd(worktrees[branch])
        return 0

    # Worktree does not exist - error
    print(f"Worktree '{branch}' does not exist", file=sys.stderr)
    if worktrees:
        print(f"Available: {', '.join(sorted(worktrees.keys()))}", file=sys.stderr)
    return 2


def handle_add(
    manager: GitWorktreeManager,
    name: str,
    base: str | None,
    config,
    commit: str | None = None,
    create_branch: bool = False,
) -> int:
    """Create new worktree."""
    worktrees = manager.list_worktrees()

    if name in worktrees:
        print(f"Worktree '{name}' already exists", file=sys.stderr)
        return 2

    try:
        if commit:
            path = manager.create_worktree(
                name,
                commit=commit,
                create_branch=create_branch,
            )
        else:
            base_branch = base or config.worktree.default_base or manager.get_main_branch()
            path = manager.create_worktree(name, base_branch)
        request_cd(path)
        return 0
    except (RuntimeError, ValueError) as e:
        print(str(e), file=sys.stderr)
        return 2


def handle_prune(manager: GitWorktreeManager) -> int:
    """Handle --prune command."""
    stale = manager.find_stale_worktrees()

    if not stale:
        print("No stale worktrees found", file=sys.stderr)
        return 1

    print(f"Found {len(stale)} stale worktrees:", file=sys.stderr)
    for branch, reason in stale:
        print(f"  {branch} ({reason})", file=sys.stderr)

    # Confirm
    try:
        response = input("Delete all? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled", file=sys.stderr)
        return 1

    if response != "y":
        print("Cancelled", file=sys.stderr)
        return 1

    # Delete
    branches = [b for b, _ in stale]
    results = manager.prune_worktrees(branches)

    errors = [f"{b}: {e}" for b, e in results.items() if e]
    success_count = len([b for b, e in results.items() if e is None])

    if errors:
        print(f"Pruned {success_count}, errors:", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        return 2

    print(f"Pruned {success_count} worktrees", file=sys.stderr)
    return 1  # Don't cd


if __name__ == "__main__":
    sys.exit(main())
