import subprocess
from textual.containers import Vertical
from textual.widgets import RichLog, Input, Static
from textual.app import ComposeResult

class TerminalPanel(Vertical):
    def __init__(self, project_root: str = "", **kwargs):
        super().__init__(**kwargs)
        self.project_root = project_root

    def compose(self) -> ComposeResult:
        yield Static("🖥️  Terminal", classes="panel-title")
        yield RichLog(id="terminal-output", markup=True, highlight=True, wrap=True)
        yield Input(placeholder="Type a command and press Enter (e.g. pytest tests/ -v)", id="terminal-input")

    def on_mount(self) -> None:
        output = self.query_one("#terminal-output", RichLog)
        output.write("[bold green]Terminal ready[/bold green]")
        output.write("[dim]Run any command — e.g. python3 -m pytest tests/ -v[/dim]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "terminal-input":
            return
        command = event.value.strip()
        if not command:
            return
        event.input.value = ""
        output = self.query_one("#terminal-output", RichLog)
        output.write(f"\n[bold cyan]$ {command}[/bold cyan]")
        self._run_command(command, output)

    def _run_command(self, command: str, output: RichLog) -> None:
        import subprocess
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.project_root,
                text=True,
            )
            result = process.communicate(timeout=30)
            if result[0]:
                for line in result[0].strip().split("\n"):
                    output.write(line)
            exit_code = process.returncode
            if exit_code == 0:
                output.write("[bold green]✅ Command completed successfully[/bold green]")
            else:
                output.write(f"[bold red]❌ Command failed (exit code: {exit_code})[/bold red]")
        except subprocess.TimeoutExpired:
            process.kill()
            output.write("[bold red]⏰ Command timed out (30s limit)[/bold red]")
        except Exception as e:
            output.write(f"[bold red]Error: {e}[/bold red]")
