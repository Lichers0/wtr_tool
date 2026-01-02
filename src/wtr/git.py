"""Git operations for worktree management."""

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from git import Repo, InvalidGitRepositoryError
from git.exc import GitCommandError


@dataclass
class BranchStatus:
    """Status information for a branch/worktree."""

    dirty: bool = False
    untracked_count: int = 0
    ahead: int = 0
    behind: int = 0
    last_commit_time: datetime | None = None
    has_stash: bool = False
    rebase_in_progress: bool = False
    merge_in_progress: bool = False


@dataclass
class CommitInfo:
    """Information about a single commit."""

    sha: str
    message: str
    time: datetime


class GitWorktreeManager:
    """Manages git worktrees for a repository."""

    def __init__(self, path: Path | None = None):
        """Initialize manager from path (defaults to cwd)."""
        self.repo = self._find_repo(path or Path.cwd())
        self.root = Path(self.repo.working_dir)
        # Container is parent directory where worktrees live side by side
        self.container = self.root.parent

    def _find_repo(self, path: Path) -> Repo:
        """Find git repository from path, walking up if needed."""
        try:
            return Repo(path, search_parent_directories=True)
        except InvalidGitRepositoryError:
            raise RuntimeError(f"Not a git repository: {path}")

    def get_main_branch(self) -> str:
        """Determine main branch name from origin/HEAD or fallback to main/master."""
        # Try to get from origin/HEAD
        try:
            ref = self.repo.git.symbolic_ref("refs/remotes/origin/HEAD", short=True)
            # ref is "origin/master" or "origin/main"
            if ref.startswith("origin/"):
                return ref[7:]  # strip "origin/"
        except Exception:
            pass

        # Fallback: check if main/master exists
        branches = [b.name for b in self.repo.branches]
        if "main" in branches:
            return "main"
        if "master" in branches:
            return "master"

        # Last resort: current branch or first branch
        current = self.get_current_branch()
        if current:
            return current

        return branches[0] if branches else "master"

    def get_main_repo_path(self) -> Path:
        """
        Get path to main repository (where .git is a directory).

        In worktree structure, this is container/<main_branch>/.
        """
        main_branch = self.get_main_branch()
        return self.container / main_branch

    def is_valid_structure(self) -> bool:
        """
        Check if repository has valid worktree structure.

        Valid structure means:
        - Root folder name matches main branch name (e.g., /project/master/)
        - Or this is already a worktree (.git is a file, not directory)
        """
        main_branch = self.get_main_branch()
        root_folder_name = self.root.name

        # If folder name matches main branch - valid
        if root_folder_name == main_branch:
            return True

        # If .git is a file (worktree link) - we're in a worktree, valid
        git_path = self.root / ".git"
        if git_path.is_file():
            return True

        return False

    def needs_restructure(self) -> bool:
        """Check if repository needs restructuring to worktree format."""
        if self.is_valid_structure():
            return False

        # Check we're on main branch
        current = self.get_current_branch()
        main = self.get_main_branch()

        return current == main

    def restructure_to_worktree(self) -> Path:
        """
        Restructure repository to worktree format.

        Transforms:
            /myproject/          (contains master branch)
                .git/
                src/

        Into:
            /myproject/          (container)
                master/          (main branch moved here)
                    .git/
                    src/

        Returns path to new root (e.g., /myproject/master/).
        """
        main_branch = self.get_main_branch()
        original_name = self.root.name
        parent = self.root.parent

        # Step 1: Rename current folder to _temp
        temp_path = parent / f"{original_name}_temp"
        self.root.rename(temp_path)

        # Step 2: Create new container with original name
        new_container = parent / original_name
        new_container.mkdir()

        # Step 3: Move _temp inside container
        temp_inside = new_container / f"{original_name}_temp"
        shutil.move(str(temp_path), str(temp_inside))

        # Step 4: Rename to main branch name
        new_root = new_container / main_branch
        temp_inside.rename(new_root)

        # Step 5: Update internal state
        self.repo = Repo(new_root)
        self.root = new_root
        self.container = new_container

        return new_root

    def list_local_branches(self) -> list[str]:
        """List all local branch names."""
        return sorted([b.name for b in self.repo.branches])

    def list_tags(self) -> list[str]:
        """List all tag names."""
        return sorted([t.name for t in self.repo.tags])

    def resolve_commit(self, commit_ish: str) -> str | None:
        """
        Resolve commit-ish to full SHA.

        Args:
            commit_ish: SHA, tag, branch, or other git ref

        Returns:
            Full SHA if found, None otherwise
        """
        try:
            commit = self.repo.commit(commit_ish)
            return commit.hexsha
        except Exception:
            return None

    def list_worktrees(self) -> dict[str, Path]:
        """
        Return dict of {name: worktree_path} for existing worktrees.

        For regular worktrees, name is the branch name.
        For detached HEAD worktrees, name is the directory name.
        """
        worktrees = {}

        # Worktrees are sibling directories in container
        if not self.container.exists():
            return worktrees

        # Include main repo as worktree
        main_branch = self.get_main_branch()
        main_repo_path = self.get_main_repo_path()
        if main_repo_path.exists():
            worktrees[main_branch] = main_repo_path

        for item in self.container.iterdir():
            if not item.is_dir():
                continue
            # Skip main repo directory (already added)
            if item == main_repo_path:
                continue
            # Check if it's a git worktree (.git file, not directory)
            git_path = item / ".git"
            if git_path.is_file():
                try:
                    wt_repo = Repo(item)
                    if wt_repo.head.is_detached:
                        # Detached HEAD - use directory name as key
                        worktrees[item.name] = item
                    else:
                        branch_name = wt_repo.active_branch.name
                        worktrees[branch_name] = item
                except Exception:
                    # Directory exists but not a valid worktree
                    pass
        return worktrees

    def branch_exists(self, name: str) -> bool:
        """Check if local branch exists."""
        return name in self.list_local_branches()

    def worktree_exists(self, branch: str) -> bool:
        """Check if worktree for branch exists."""
        return branch in self.list_worktrees()

    def get_worktree_path(self, branch: str) -> Path:
        """Get path where worktree for branch would be located."""
        return self.container / branch

    def create_worktree(
        self,
        name: str,
        base_branch: str | None = None,
        commit: str | None = None,
        create_branch: bool = False,
    ) -> Path:
        """
        Create worktree.

        Args:
            name: Directory name for worktree (also branch name if creating branch)
            base_branch: Base branch for new worktree (mutually exclusive with commit)
            commit: Commit SHA or tag for detached HEAD (mutually exclusive with base_branch)
            create_branch: If True with commit, create new branch instead of detached HEAD

        Returns:
            Path to created worktree

        Raises:
            ValueError: Invalid argument combination
            RuntimeError: Git operation failed

        Examples:
            create_worktree("feature")              # existing branch or new from main
            create_worktree("feature", "develop")   # new branch from develop
            create_worktree("abc1234", commit="abc1234")  # detached HEAD
            create_worktree("hotfix", commit="abc1234", create_branch=True)  # branch from commit
        """
        if commit and base_branch:
            raise ValueError("commit and base_branch are mutually exclusive")

        worktree_path = self.get_worktree_path(name)

        if worktree_path.exists():
            raise RuntimeError(f"Directory already exists: {worktree_path}")

        try:
            if commit:
                # Verify commit exists
                resolved = self.resolve_commit(commit)
                if not resolved:
                    raise RuntimeError(f"Commit '{commit}' not found")

                if create_branch:
                    # Create new branch from commit
                    self.repo.git.worktree("add", "-b", name, str(worktree_path), commit)
                else:
                    # Detached HEAD
                    self.repo.git.worktree("add", "--detach", str(worktree_path), commit)
            elif self.branch_exists(name):
                # Branch exists, just create worktree
                self.repo.git.worktree("add", str(worktree_path), name)
            else:
                # Create new branch from base
                base = base_branch or self.get_main_branch()
                self.repo.git.worktree("add", "-b", name, str(worktree_path), base)
        except GitCommandError as e:
            raise RuntimeError(f"Failed to create worktree: {e}")

        return worktree_path

    def delete_worktree(self, branch: str) -> None:
        """Delete worktree for branch (keeps the branch itself)."""
        worktrees = self.list_worktrees()

        if branch not in worktrees:
            raise RuntimeError(f"No worktree for branch: {branch}")

        worktree_path = worktrees[branch]

        try:
            # Remove from git
            self.repo.git.worktree("remove", str(worktree_path), "--force")
        except GitCommandError as e:
            raise RuntimeError(f"Failed to delete worktree: {e}")

    def get_current_branch(self) -> str | None:
        """Get current branch name or None if detached."""
        if self.repo.head.is_detached:
            return None
        return self.repo.active_branch.name

    def get_worktree_list_raw(self) -> list[tuple[Path, str | None]]:
        """
        Get raw worktree list from git worktree list command.

        Returns:
            List of (path, branch_name) tuples. branch_name is None for detached HEAD.
        """
        result = []
        try:
            output = self.repo.git.worktree("list", "--porcelain")
            current_path = None

            for line in output.split("\n"):
                if line.startswith("worktree "):
                    current_path = Path(line[9:])
                elif line.startswith("branch refs/heads/"):
                    branch = line[18:]  # strip "branch refs/heads/"
                    if current_path:
                        result.append((current_path, branch))
                        current_path = None
                elif line == "detached":
                    if current_path:
                        result.append((current_path, None))
                        current_path = None
        except Exception:
            pass

        return result

    def find_main_worktree_path(self) -> Path | None:
        """
        Find path to main branch worktree from git worktree list.

        Returns:
            Path to main branch worktree, or None if not found.
        """
        main_branch = self.get_main_branch()
        worktree_list = self.get_worktree_list_raw()

        for path, branch in worktree_list:
            if branch == main_branch:
                return path

        return None

    def has_multiple_worktrees(self) -> bool:
        """Check if there are multiple worktrees (more than just main repo)."""
        return len(self.get_worktree_list_raw()) > 1

    def get_branch_status(self, branch: str) -> BranchStatus:
        """Get detailed status for a branch."""
        status = BranchStatus()

        # Find the repo to check - either worktree or main repo
        worktrees = self.list_worktrees()
        if branch in worktrees:
            try:
                repo = Repo(worktrees[branch])
            except Exception:
                return status
        elif branch == self.get_current_branch():
            repo = self.repo
        else:
            # Branch exists but no worktree - get last commit time only
            try:
                branch_ref = self.repo.heads[branch]
                status.last_commit_time = datetime.fromtimestamp(
                    branch_ref.commit.committed_date
                )
            except Exception:
                pass
            return status

        # Check dirty status
        status.dirty = repo.is_dirty(untracked_files=False)

        # Count untracked files
        status.untracked_count = len(repo.untracked_files)

        # Check ahead/behind
        try:
            branch_ref = repo.active_branch
            tracking = branch_ref.tracking_branch()
            if tracking:
                ahead = len(list(repo.iter_commits(f"{tracking}..{branch_ref}")))
                behind = len(list(repo.iter_commits(f"{branch_ref}..{tracking}")))
                status.ahead = ahead
                status.behind = behind
        except Exception:
            pass

        # Last commit time
        try:
            status.last_commit_time = datetime.fromtimestamp(
                repo.head.commit.committed_date
            )
        except Exception:
            pass

        # Check for stash
        try:
            stash_list = repo.git.stash("list")
            status.has_stash = bool(stash_list.strip())
        except Exception:
            pass

        # Check rebase in progress
        git_dir = Path(repo.git_dir)
        status.rebase_in_progress = (
            (git_dir / "rebase-merge").exists()
            or (git_dir / "rebase-apply").exists()
        )

        # Check merge in progress
        status.merge_in_progress = (git_dir / "MERGE_HEAD").exists()

        return status

    def get_recent_commits(self, branch: str, count: int = 5) -> list[CommitInfo]:
        """Get recent commits for a branch."""
        commits = []
        try:
            branch_ref = self.repo.heads[branch]
            for commit in list(branch_ref.commit.iter_parents())[:count]:
                commits.append(
                    CommitInfo(
                        sha=commit.hexsha[:7],
                        message=commit.message.split("\n")[0][:60],
                        time=datetime.fromtimestamp(commit.committed_date),
                    )
                )
            # Include the branch tip commit itself
            tip = branch_ref.commit
            commits.insert(
                0,
                CommitInfo(
                    sha=tip.hexsha[:7],
                    message=tip.message.split("\n")[0][:60],
                    time=datetime.fromtimestamp(tip.committed_date),
                ),
            )
            commits = commits[:count]
        except Exception:
            pass
        return commits

    def is_branch_merged(self, branch: str, into: str | None = None) -> bool:
        """Check if branch is merged into target branch."""
        target = into or self.get_main_branch()
        try:
            # Check if branch commit is ancestor of target
            branch_commit = self.repo.heads[branch].commit
            target_commit = self.repo.heads[target].commit
            return self.repo.is_ancestor(branch_commit, target_commit)
        except Exception:
            return False

    def find_stale_worktrees(self) -> list[tuple[str, str]]:
        """
        Find worktrees that can be pruned.

        Returns list of (branch_name, reason) tuples.
        Reasons: "branch deleted", "merged to main"
        """
        stale = []
        worktrees = self.list_worktrees()
        local_branches = set(self.list_local_branches())
        main_branch = self.get_main_branch()

        for branch in worktrees:
            # Check if branch was deleted
            if branch not in local_branches:
                stale.append((branch, "branch deleted"))
                continue

            # Check if merged to main (skip main itself)
            if branch != main_branch and self.is_branch_merged(branch, main_branch):
                stale.append((branch, f"merged to {main_branch}"))

        return stale

    def prune_worktrees(self, branches: list[str]) -> dict[str, str | None]:
        """
        Delete multiple worktrees.

        Returns dict of {branch: error_message or None}.
        """
        results = {}
        for branch in branches:
            try:
                self.delete_worktree(branch)
                results[branch] = None
            except RuntimeError as e:
                results[branch] = str(e)
        return results

    def get_uncommitted_files(self, branch: str) -> list[str]:
        """
        Get list of uncommitted files in worktree for branch.

        Returns empty list if no worktree exists or working tree is clean.
        """
        worktrees = self.list_worktrees()
        if branch not in worktrees:
            # Check if it's the current branch in main repo
            if branch == self.get_current_branch():
                repo = self.repo
            else:
                return []
        else:
            try:
                repo = Repo(worktrees[branch])
            except Exception:
                return []

        files = []

        # Modified files (staged and unstaged)
        for item in repo.index.diff(None):
            files.append(item.a_path)

        # Staged files
        for item in repo.index.diff("HEAD"):
            if item.a_path not in files:
                files.append(item.a_path)

        # Untracked files
        files.extend(repo.untracked_files)

        return sorted(set(files))


SHARE_OBJ_FILENAME = "share_obj.yaml"


def create_shared_symlinks(worktree_path: Path, container: Path) -> list[str]:
    """
    Create symlinks in new worktree based on share_obj.yaml.

    Args:
        worktree_path: Path to newly created worktree
        container: Path to container directory (parent of all worktrees)

    Returns:
        List of warning messages (empty if all ok)
    """
    warnings = []
    share_obj_file = container / SHARE_OBJ_FILENAME

    if not share_obj_file.exists():
        return warnings

    try:
        import yaml
        with open(share_obj_file) as f:
            share_obj = yaml.safe_load(f) or {}
    except Exception as e:
        warnings.append(f"Failed to read {SHARE_OBJ_FILENAME}: {e}")
        return warnings

    worktree_name = worktree_path.name

    for source_dir, items in share_obj.items():
        # Skip if source is the worktree itself
        if source_dir == worktree_name:
            continue

        if not isinstance(items, list):
            warnings.append(f"Invalid format for '{source_dir}': expected list")
            continue

        source_path = container / source_dir

        for item in items:
            symlink_path = worktree_path / item
            target = Path("..") / source_dir / item

            # Check if source exists (warning only, still create symlink)
            item_source_path = source_path / item
            if not item_source_path.exists():
                warnings.append(f"Source does not exist: {source_dir}/{item}")

            try:
                symlink_path.symlink_to(target)
            except OSError as e:
                warnings.append(f"Failed to create symlink {item}: {e}")

    return warnings
