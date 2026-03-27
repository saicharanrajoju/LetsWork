from textual.containers import Vertical
from textual.widgets import RichLog, Static
from textual.app import ComposeResult
from src.events import EventType

class ApprovalPanel(Vertical):
    BINDINGS = [("a", "approve", "Approve"), ("r", "reject", "Reject")]

    def __init__(self, approval_queue, event_log, **kwargs):
        super().__init__(**kwargs)
        self.approval_queue = approval_queue
        self.event_log = event_log

    def compose(self) -> ComposeResult:
        yield Static("⚠️  Pending Approvals", classes="panel-title")
        yield RichLog(id="approval-log", markup=True, highlight=True, wrap=True)

    def on_mount(self) -> None:
        self.refresh_pending()
        self.event_log.on_event(self._on_event)

    def _on_event(self, event) -> None:
        if event.event_type == EventType.FILE_WRITE:
            self.refresh_pending()

    def refresh_pending(self) -> None:
        log = self.query_one("#approval-log", RichLog)
        log.clear()
        pending = self.approval_queue.get_pending()
        
        if not pending:
            log.write("[dim]No pending changes[/dim]")
            return
            
        for change in pending:
            log.write(f"[bold yellow]━━━ Change {change.id} ━━━[/bold yellow]")
            log.write(f"[bold]File:[/bold] {change.path}")
            log.write(f"[bold]By:[/bold] {change.user_id}")
            log.write(f"[bold]Time:[/bold] {change.timestamp.strftime('%H:%M:%S')}")
            diff = self.approval_queue.get_diff(change.id)
            for line in diff.split("\n"):
                if line.startswith("++") or line.startswith("--"):
                    log.write(f"[bold]{line}[/bold]")
                elif line.startswith("+"):
                    log.write(f"[green]{line}[/green]")
                elif line.startswith("-"):
                    log.write(f"[red]{line}[/red]")
                elif line.startswith("@@"):
                    log.write(f"[cyan]{line}[/cyan]")
                else:
                    log.write(line)
            log.write("")
            
        log.write("[bold]Press [A] to approve top change, [R] to reject[/bold]")

    def action_approve(self) -> None:
        pending = self.approval_queue.get_pending()
        if not pending:
            return
            
        change = pending[0]
        self.approval_queue.approve(change.id)
        self.event_log.emit(EventType.FILE_WRITE, change.user_id, {"path": change.path, "status": "approved", "change_id": change.id})
        log = self.query_one("#approval-log", RichLog)
        log.write(f"[bold green]✅ Approved: {change.path} by {change.user_id} (ID: {change.id}) — written to disk[/bold green]")
        self.refresh_pending()

    def action_reject(self) -> None:
        pending = self.approval_queue.get_pending()
        if not pending:
            return
            
        change = pending[0]
        self.approval_queue.reject(change.id)
        self.event_log.emit(EventType.FILE_WRITE, change.user_id, {"path": change.path, "status": "rejected", "change_id": change.id})
        log = self.query_one("#approval-log", RichLog)
        log.write(f"[bold red]❌ Rejected: {change.path} by {change.user_id} (ID: {change.id}) — discarded[/bold red]")
        self.refresh_pending()
