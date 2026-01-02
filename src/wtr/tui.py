"""TUI interface for worktree manager."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from .config import Config, load_config
from .fuzzy import fuzzy_match
from .git import BranchStatus, GitWorktreeManager, create_shared_symlinks


def format_time_ago(dt: datetime | None) -> str:
    """Format datetime as relative time string."""
    if dt is None:
        return ""
    now = datetime.now()
    diff = now - dt
    seconds = diff.total_seconds()

    if seconds < 60:
        return "now"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m"
    elif seconds < 86400:
        return f"{int(seconds // 3600)}h"
    else:
        return f"{int(seconds // 86400)}d"


class ConfirmDialog(ModalScreen[bool]):
    """Modal dialog for yes/no confirmation."""

    CSS = """
    ConfirmDialog {
        align: center middle;
    }
    ConfirmDialog > Container {
        width: 50;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    ConfirmDialog Label {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }
    ConfirmDialog Horizontal {
        width: 100%;
        height: auto;
        align: center middle;
    }
    ConfirmDialog Button {
        margin: 0 1;
    }
    """

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self.message)
            with Horizontal():
                yield Button("Yes", id="yes", variant="primary")
                yield Button("No", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class AlertDialog(ModalScreen[None]):
    """Modal dialog for alert messages."""

    CSS = """
    AlertDialog {
        align: center middle;
    }
    AlertDialog > Container {
        width: 60;
        height: auto;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    AlertDialog Label {
        width: 100%;
        margin-bottom: 1;
    }
    AlertDialog Button {
        width: 100%;
    }
    """

    def __init__(self, message: str):
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self.message)
            yield Button("OK", id="ok", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


@dataclass
class CreateWorktreeResult:
    """Result from CreateWorktreeDialog."""

    name: str
    base_branch: str | None = None
    commit: str | None = None
    create_branch: bool = False


class CreateWorktreeDialog(ModalScreen[CreateWorktreeResult | None]):
    """Dialog for creating new worktree with mode selection."""

    CSS = """
    CreateWorktreeDialog {
        align: center middle;
    }
    CreateWorktreeDialog > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    CreateWorktreeDialog .title {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    CreateWorktreeDialog .field-label {
        margin-top: 1;
    }
    CreateWorktreeDialog Input {
        width: 100%;
    }
    CreateWorktreeDialog #mode-buttons {
        width: 100%;
        height: auto;
        align: center middle;
        margin-bottom: 1;
    }
    CreateWorktreeDialog .mode-btn {
        margin: 0 1;
    }
    CreateWorktreeDialog .mode-btn.-active {
        background: $primary;
    }
    CreateWorktreeDialog #suggestion-list {
        height: 6;
        border: solid $secondary;
        margin-bottom: 1;
    }
    CreateWorktreeDialog #checkbox-container {
        height: auto;
        margin-top: 1;
    }
    CreateWorktreeDialog Horizontal {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    CreateWorktreeDialog Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        worktree_name: str,
        default_base: str,
        branches: list[str],
        tags: list[str],
        is_new_branch: bool,
    ):
        super().__init__()
        self.worktree_name = worktree_name
        self.default_base = default_base
        self.branches = branches
        self.tags = tags
        self.is_new_branch = is_new_branch
        self._filtered_items: list[str] = []
        self._mode = "branch"  # "branch", "commit", "tag"

    def compose(self) -> ComposeResult:
        with Container():
            yield Label("Create worktree", classes="title")
            yield Label(f"Name: {self.worktree_name}")

            # Mode selection buttons
            with Horizontal(id="mode-buttons"):
                yield Button("Branch", id="mode-branch", classes="mode-btn -active")
                yield Button("Commit", id="mode-commit", classes="mode-btn")
                yield Button("Tag", id="mode-tag", classes="mode-btn")

            # Dynamic field label
            yield Label("Base branch:", id="field-label", classes="field-label")
            yield Input(value=self.default_base, id="value-input")
            yield ListView(id="suggestion-list")

            # Create branch checkbox (hidden by default)
            with Container(id="checkbox-container"):
                yield Checkbox("Create new branch", id="create-branch", value=False)

            with Horizontal():
                yield Button("Create", id="create", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_mount(self) -> None:
        self._update_mode("branch")
        self.query_one("#value-input", Input).focus()

    def _update_mode(self, mode: str) -> None:
        """Update UI based on selected mode."""
        self._mode = mode

        # Update button styles
        for btn_id in ["mode-branch", "mode-commit", "mode-tag"]:
            btn = self.query_one(f"#{btn_id}", Button)
            if btn_id == f"mode-{mode}":
                btn.add_class("-active")
            else:
                btn.remove_class("-active")

        # Update field label
        label = self.query_one("#field-label", Label)
        input_field = self.query_one("#value-input", Input)
        checkbox_container = self.query_one("#checkbox-container", Container)
        checkbox = self.query_one("#create-branch", Checkbox)

        if mode == "branch":
            label.update("Base branch:")
            input_field.value = self.default_base
            checkbox_container.display = False
        elif mode == "commit":
            label.update("Commit SHA:")
            input_field.value = ""
            checkbox_container.display = True
            checkbox.value = False
        elif mode == "tag":
            label.update("Tag:")
            input_field.value = ""
            checkbox_container.display = True
            checkbox.value = False

        self._refresh_suggestions(input_field.value)

    def _refresh_suggestions(self, filter_text: str = "") -> None:
        """Refresh suggestion list based on mode and filter."""
        list_view = self.query_one("#suggestion-list", ListView)
        list_view.clear()

        if self._mode == "branch":
            items = self.branches
        elif self._mode == "tag":
            items = self.tags
        else:
            # No suggestions for commit SHA
            self._filtered_items = []
            return

        self._filtered_items = fuzzy_match(items, filter_text)
        for item in self._filtered_items[:10]:  # Limit to 10
            list_view.append(ListItem(Label(item)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id

        # Mode buttons
        if btn_id == "mode-branch":
            self._update_mode("branch")
            return
        elif btn_id == "mode-commit":
            self._update_mode("commit")
            return
        elif btn_id == "mode-tag":
            self._update_mode("tag")
            return

        # Action buttons
        if btn_id == "create":
            self._submit()
        else:
            self.dismiss(None)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "value-input":
            self._refresh_suggestions(event.value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        list_view = self.query_one("#suggestion-list", ListView)
        if list_view.index is not None and self._filtered_items:
            selected = self._filtered_items[list_view.index]
            input_field = self.query_one("#value-input", Input)
            input_field.value = selected
            self._submit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "value-input":
            self._submit()

    def _submit(self) -> None:
        """Submit the dialog with current values."""
        value = self.query_one("#value-input", Input).value.strip()
        if not value:
            return

        if self._mode == "branch":
            result = CreateWorktreeResult(
                name=self.worktree_name,
                base_branch=value,
            )
        else:
            # commit or tag mode
            create_branch = self.query_one("#create-branch", Checkbox).value
            result = CreateWorktreeResult(
                name=self.worktree_name,
                commit=value,
                create_branch=create_branch,
            )

        self.dismiss(result)


class WorktreeActionDialog(ModalScreen[str | None]):
    """Dialog for actions on existing worktree."""

    CSS = """
    WorktreeActionDialog {
        align: center middle;
    }
    WorktreeActionDialog > Container {
        width: 50;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    WorktreeActionDialog .title {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    WorktreeActionDialog .path {
        width: 100%;
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }
    WorktreeActionDialog Horizontal {
        width: 100%;
        height: auto;
        align: center middle;
    }
    WorktreeActionDialog Button {
        margin: 0 1;
    }
    """

    def __init__(self, branch: str, path: Path):
        super().__init__()
        self.branch = branch
        self.path = path

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(f"Worktree: {self.branch}", classes="title")
            yield Label(str(self.path), classes="path")
            with Horizontal():
                yield Button("Go", id="goto", variant="primary")
                yield Button("Delete", id="delete", variant="error")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in ("goto", "delete"):
            self.dismiss(event.button.id)
        else:
            self.dismiss(None)


class PruneDialog(ModalScreen[list[str] | None]):
    """Dialog for selecting stale worktrees to prune."""

    CSS = """
    PruneDialog {
        align: center middle;
    }
    PruneDialog > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    PruneDialog .title {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    PruneDialog .item {
        height: auto;
        margin: 0 0 1 0;
    }
    PruneDialog .reason {
        color: $text-muted;
        margin-left: 2;
    }
    PruneDialog Horizontal {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    PruneDialog Button {
        margin: 0 1;
    }
    """

    def __init__(self, stale: list[tuple[str, str]]):
        super().__init__()
        self.stale = stale

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(f"Found {len(self.stale)} stale worktrees:", classes="title")
            for branch, reason in self.stale:
                with Horizontal(classes="item"):
                    yield Checkbox(branch, value=True, id=f"cb-{branch}")
                    yield Label(f"({reason})", classes="reason")
            with Horizontal():
                yield Button("Delete selected", id="delete", variant="error")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "delete":
            selected = []
            for branch, _ in self.stale:
                cb = self.query_one(f"#cb-{branch}", Checkbox)
                if cb.value:
                    selected.append(branch)
            self.dismiss(selected if selected else None)
        else:
            self.dismiss(None)


class MultiDeleteDialog(ModalScreen[bool]):
    """Dialog for confirming multi-delete."""

    CSS = """
    MultiDeleteDialog {
        align: center middle;
    }
    MultiDeleteDialog > Container {
        width: 50;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    MultiDeleteDialog .title {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    MultiDeleteDialog .branch {
        margin-left: 2;
    }
    MultiDeleteDialog Horizontal {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    MultiDeleteDialog Button {
        margin: 0 1;
    }
    """

    def __init__(self, branches: list[str]):
        super().__init__()
        self.branches = branches

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(f"Delete {len(self.branches)} worktrees?", classes="title")
            for branch in self.branches:
                yield Label(f"- {branch}", classes="branch")
            with Horizontal():
                yield Button("Delete", id="delete", variant="error")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "delete")


class UncommittedWarningDialog(ModalScreen[bool]):
    """Dialog warning about uncommitted changes in base branch."""

    CSS = """
    UncommittedWarningDialog {
        align: center middle;
    }
    UncommittedWarningDialog > Container {
        width: 60;
        height: auto;
        max-height: 80%;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    UncommittedWarningDialog .title {
        width: 100%;
        text-align: center;
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    UncommittedWarningDialog .branch-info {
        margin-bottom: 1;
    }
    UncommittedWarningDialog .files-label {
        text-style: bold;
        margin-bottom: 1;
    }
    UncommittedWarningDialog .file-item {
        color: $text-muted;
        margin-left: 2;
    }
    UncommittedWarningDialog Horizontal {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }
    UncommittedWarningDialog Button {
        margin: 0 1;
    }
    """

    def __init__(self, branch: str, files: list[str]):
        super().__init__()
        self.branch = branch
        self.files = files[:10]  # Limit to 10 files
        self.has_more = len(files) > 10

    def compose(self) -> ComposeResult:
        with Container():
            yield Label("⚠ Uncommitted changes in base branch", classes="title")
            yield Label(f"Branch: {self.branch}", classes="branch-info")
            yield Label("Modified files:", classes="files-label")
            for f in self.files:
                yield Label(f"• {f}", classes="file-item")
            if self.has_more:
                yield Label(f"  ... and {len(self.files) - 10} more", classes="file-item")
            with Horizontal():
                yield Button("Continue anyway", id="continue", variant="warning")
                yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "continue")


class BranchItem(ListItem):
    """List item representing a branch with status indicators."""

    def __init__(
        self,
        branch: str,
        has_worktree: bool,
        is_current: bool,
        status: BranchStatus,
        selected: bool = False,
    ):
        super().__init__()
        self.branch = branch
        self.has_worktree = has_worktree
        self.is_current = is_current
        self.status = status
        self.selected_for_delete = selected

    # Column widths for alignment
    BRANCH_WIDTH = 20
    STATUS_WIDTH = 12
    SYNC_WIDTH = 8

    def compose(self) -> ComposeResult:
        # Column 1: Worktree indicator (emoji = 2 visual chars)
        wt_icon = "📁" if self.has_worktree else "· "

        # Column 2: Current/select indicator (fixed 2 chars)
        if self.selected_for_delete:
            current_icon = "☑ "
        elif self.is_current:
            current_icon = "● "
        else:
            current_icon = "  "

        # Column 3: Branch name (fixed width, left-aligned)
        branch_col = f"{self.branch:<{self.BRANCH_WIDTH}}"

        # Column 4: Status indicators (fixed width)
        status_parts = []
        if self.status.dirty:
            status_parts.append("*")
        if self.status.untracked_count > 0:
            status_parts.append(f"[+{self.status.untracked_count}]")
        if self.status.rebase_in_progress:
            status_parts.append("[R]")
        elif self.status.merge_in_progress:
            status_parts.append("[M]")
        if self.status.has_stash:
            status_parts.append("[S]")
        status_col = f"{' '.join(status_parts):<{self.STATUS_WIDTH}}"

        # Column 5: Ahead/behind (fixed width)
        ab_parts = []
        if self.status.ahead > 0:
            ab_parts.append(f"↑{self.status.ahead}")
        if self.status.behind > 0:
            ab_parts.append(f"↓{self.status.behind}")
        sync_col = f"{' '.join(ab_parts):<{self.SYNC_WIDTH}}"

        # Column 6: Last commit time
        time_col = format_time_ago(self.status.last_commit_time)

        # Combine all columns
        line = f"{wt_icon} {current_icon}{branch_col} {status_col} {sync_col} {time_col}"
        yield Label(line)


class WorktreeApp(App[Path | None]):
    """Main TUI application for worktree management."""

    CSS = """
    Screen {
        background: $surface;
    }
    #main-container {
        padding: 1 2;
    }
    #input-container {
        height: auto;
        margin-bottom: 1;
    }
    #branch-input {
        width: 100%;
    }
    #branches-label {
        margin-top: 1;
        margin-bottom: 1;
        text-style: bold;
    }
    #branch-list {
        height: 1fr;
        min-height: 5;
        border: solid $primary;
    }
    #preview-container {
        height: auto;
        max-height: 8;
        margin-top: 1;
        border: solid $secondary;
        padding: 0 1;
    }
    #preview-label {
        text-style: bold;
    }
    .commit-line {
        color: $text-muted;
    }
    #status {
        height: auto;
        margin-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit"),
        Binding("d", "delete", "Delete"),
        Binding("p", "prune", "Prune"),
        Binding("space", "toggle_select", "Multi-select", show=False),
        Binding("enter", "select", "Select", show=False),
    ]

    def __init__(self, manager: GitWorktreeManager, config: Config | None = None):
        super().__init__()
        self.manager = manager
        self.config = config or load_config(manager.root)
        self.worktrees = manager.list_worktrees()
        self.branches = manager.list_local_branches()
        self.tags = manager.list_tags()
        self.current_branch = manager.get_current_branch()
        # Base branch for new worktrees (branch where app was launched)
        self.base_branch = self.current_branch or manager.get_main_branch()
        self.result_path: Path | None = None
        self.selected_branches: set[str] = set()
        self._status_cache: dict[str, BranchStatus] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="main-container"):
            with Container(id="input-container"):
                yield Input(placeholder="Filter branches...", id="branch-input")
            yield Label("Branches:", id="branches-label")
            yield ListView(id="branch-list")
            if self.config.ui.show_preview:
                with Vertical(id="preview-container"):
                    yield Label("Preview:", id="preview-label")
                    yield Static("", id="preview-content")
            yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_branch_list()
        self.query_one("#branch-input", Input).focus()

        # Check for stale worktrees on startup
        if self.config.prune.auto_suggest:
            stale = self.manager.find_stale_worktrees()
            if stale:
                self._update_status(f"Found {len(stale)} stale worktrees. Press 'p' to prune.")

    def _get_branch_status(self, branch: str) -> BranchStatus:
        """Get cached branch status."""
        if branch not in self._status_cache:
            self._status_cache[branch] = self.manager.get_branch_status(branch)
        return self._status_cache[branch]

    def _refresh_branch_list(self, filter_text: str = "") -> None:
        """Refresh the branch list, optionally filtering with fuzzy search."""
        self.worktrees = self.manager.list_worktrees()
        self._status_cache.clear()
        list_view = self.query_one("#branch-list", ListView)
        list_view.clear()

        # Use fuzzy matching
        filtered = fuzzy_match(self.branches, filter_text)

        for branch in filtered:
            has_wt = branch in self.worktrees
            is_current = branch == self.current_branch
            status = self._get_branch_status(branch) if self.config.ui.show_status else BranchStatus()
            selected = branch in self.selected_branches
            list_view.append(BranchItem(branch, has_wt, is_current, status, selected))

        # Auto-select first item
        if len(list_view.children) > 0:
            list_view.index = 0

    def _update_preview(self, branch: str) -> None:
        """Update commit preview for branch."""
        if not self.config.ui.show_preview:
            return

        preview = self.query_one("#preview-content", Static)
        commits = self.manager.get_recent_commits(branch, self.config.ui.preview_count)

        if not commits:
            preview.update("No commits")
            return

        lines = []
        for commit in commits:
            time_ago = format_time_ago(commit.time)
            lines.append(f"{commit.sha} {commit.message} ({time_ago})")

        preview.update("\n".join(lines))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "branch-input":
            self._refresh_branch_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter in filter input - always create new branch."""
        if event.input.id == "branch-input":
            branch_name = event.value.strip()
            if branch_name:
                # Always open create dialog for new branch
                is_new = not self.manager.branch_exists(branch_name)
                self.push_screen(
                    CreateWorktreeDialog(
                        branch_name,
                        self.base_branch,
                        self.branches,
                        self.tags,
                        is_new,
                    ),
                    self._on_create_dialog,
                )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle Enter on branch list - switch to existing or create worktree."""
        if isinstance(event.item, BranchItem):
            branch = event.item.branch
            if branch in self.worktrees:
                # Worktree exists - ask to switch
                self._selected_branch_for_switch = branch
                self.push_screen(
                    ConfirmDialog(f"Switch to {branch}?"),
                    self._on_switch_confirm,
                )
            else:
                # No worktree - create it
                is_new = not self.manager.branch_exists(branch)
                self.push_screen(
                    CreateWorktreeDialog(
                        branch,
                        self.base_branch,
                        self.branches,
                        self.tags,
                        is_new,
                    ),
                    self._on_create_dialog,
                )

    def _on_switch_confirm(self, confirm: bool) -> None:
        """Handle switch confirmation for existing worktree."""
        if confirm and hasattr(self, "_selected_branch_for_switch"):
            branch = self._selected_branch_for_switch
            if branch in self.worktrees:
                self.result_path = self.worktrees[branch]
                self.exit(self.result_path)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, BranchItem):
            self._update_preview(event.item.branch)

    def _on_worktree_action(self, action: str | None) -> None:
        """Handle worktree action dialog result."""
        if action == "goto":
            list_view = self.query_one("#branch-list", ListView)
            if list_view.highlighted_child and isinstance(list_view.highlighted_child, BranchItem):
                branch = list_view.highlighted_child.branch
                if branch in self.worktrees:
                    self.result_path = self.worktrees[branch]
                    self.exit(self.result_path)
        elif action == "delete":
            list_view = self.query_one("#branch-list", ListView)
            if list_view.highlighted_child and isinstance(list_view.highlighted_child, BranchItem):
                branch = list_view.highlighted_child.branch
                self._delete_worktree(branch)

    def _on_create_dialog(self, result: CreateWorktreeResult | None) -> None:
        """Handle create dialog result."""
        if result is None:
            return

        # Store for later use in callbacks
        self._pending_create = result

        # Check for uncommitted files in base branch (only for branch mode)
        if result.base_branch:
            uncommitted = self.manager.get_uncommitted_files(result.base_branch)
            if uncommitted:
                self.push_screen(
                    UncommittedWarningDialog(result.base_branch, uncommitted),
                    self._on_uncommitted_warning,
                )
                return

        self._do_create_worktree(result)

    def _on_uncommitted_warning(self, proceed: bool) -> None:
        """Handle uncommitted warning dialog result."""
        if proceed and hasattr(self, "_pending_create"):
            self._do_create_worktree(self._pending_create)

    def _do_create_worktree(self, result: CreateWorktreeResult) -> None:
        """Actually create the worktree."""
        try:
            if result.commit:
                path = self.manager.create_worktree(
                    result.name,
                    commit=result.commit,
                    create_branch=result.create_branch,
                )
            else:
                path = self.manager.create_worktree(
                    result.name,
                    base_branch=result.base_branch,
                )

            # Create shared symlinks
            warnings = create_shared_symlinks(path, self.manager.container)

            self._update_status(f"Created worktree: {path}")
            self.worktrees = self.manager.list_worktrees()
            self._refresh_branch_list()

            if warnings:
                # Show warnings first, then ask to go
                alert_msg = "❗ " + "\n❗ ".join(warnings)
                self.push_screen(
                    AlertDialog(alert_msg),
                    lambda _: self.push_screen(
                        ConfirmDialog(f"Go to {result.name}?"),
                        lambda go: self._on_goto_confirm(go, path),
                    ),
                )
            else:
                self.push_screen(
                    ConfirmDialog(f"Go to {result.name}?"),
                    lambda go: self._on_goto_confirm(go, path),
                )
        except (RuntimeError, ValueError) as e:
            self._update_status(f"Error: {e}")

    def _on_goto_confirm(self, go: bool, path: Path) -> None:
        """Handle goto confirmation."""
        if go:
            self.result_path = path
            self.exit(self.result_path)

    def _delete_worktree(self, branch: str) -> None:
        """Delete worktree after confirmation."""
        self.push_screen(
            ConfirmDialog(f"Delete worktree '{branch}'?"),
            lambda confirm: self._on_delete_confirm(confirm, branch),
        )

    def _on_delete_confirm(self, confirm: bool, branch: str) -> None:
        """Handle delete confirmation."""
        if not confirm:
            return
        try:
            self.manager.delete_worktree(branch)
            self._update_status(f"Deleted worktree: {branch}")
            self._refresh_branch_list()
        except RuntimeError as e:
            self._update_status(f"Error: {e}")

    def action_delete(self) -> None:
        """Handle delete key binding."""
        # Check for multi-select first
        if self.selected_branches:
            selected_with_wt = [b for b in self.selected_branches if b in self.worktrees]
            if selected_with_wt:
                self.push_screen(
                    MultiDeleteDialog(selected_with_wt),
                    self._on_multi_delete_confirm,
                )
            return

        # Single delete
        list_view = self.query_one("#branch-list", ListView)
        if list_view.highlighted_child and isinstance(list_view.highlighted_child, BranchItem):
            branch = list_view.highlighted_child.branch
            if branch in self.worktrees:
                self._delete_worktree(branch)

    def _on_multi_delete_confirm(self, confirm: bool) -> None:
        """Handle multi-delete confirmation."""
        if not confirm:
            return

        selected_with_wt = [b for b in self.selected_branches if b in self.worktrees]
        results = self.manager.prune_worktrees(selected_with_wt)

        errors = [f"{b}: {e}" for b, e in results.items() if e]
        success_count = len([b for b, e in results.items() if e is None])

        self.selected_branches.clear()
        self._refresh_branch_list()

        if errors:
            self._update_status(f"Deleted {success_count}, errors: {'; '.join(errors)}")
        else:
            self._update_status(f"Deleted {success_count} worktrees")

    def action_toggle_select(self) -> None:
        """Toggle multi-select for current branch."""
        list_view = self.query_one("#branch-list", ListView)
        if list_view.highlighted_child and isinstance(list_view.highlighted_child, BranchItem):
            branch = list_view.highlighted_child.branch
            if branch in self.selected_branches:
                self.selected_branches.remove(branch)
            else:
                self.selected_branches.add(branch)
            self._refresh_branch_list(self.query_one("#branch-input", Input).value)

    def action_prune(self) -> None:
        """Show prune dialog for stale worktrees."""
        stale = self.manager.find_stale_worktrees()
        if not stale:
            self._update_status("No stale worktrees found")
            return

        self.push_screen(PruneDialog(stale), self._on_prune_dialog)

    def _on_prune_dialog(self, selected: list[str] | None) -> None:
        """Handle prune dialog result."""
        if not selected:
            return

        results = self.manager.prune_worktrees(selected)
        errors = [f"{b}: {e}" for b, e in results.items() if e]
        success_count = len([b for b, e in results.items() if e is None])

        self._refresh_branch_list()

        if errors:
            self._update_status(f"Pruned {success_count}, errors: {'; '.join(errors)}")
        else:
            self._update_status(f"Pruned {success_count} worktrees")

    def action_quit(self) -> None:
        """Quit without result."""
        self.exit(None)

    def _update_status(self, message: str) -> None:
        """Update status bar."""
        self.query_one("#status", Static).update(message)


def run_tui(manager: GitWorktreeManager, config: Config | None = None) -> Path | None:
    """Run TUI and return selected path or None."""
    app = WorktreeApp(manager, config)
    return app.run()
