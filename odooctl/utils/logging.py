from __future__ import annotations

from rich.console import Console

console = Console()

def info(message: str) -> None:
    console.print(f"[cyan]•[/cyan] {message}")

def success(message: str) -> None:
    console.print(f"[green]✓[/green] {message}")

def warn(message: str) -> None:
    console.print(f"[yellow]![/yellow] {message}")

def error(message: str) -> None:
    console.print(f"[red]✗[/red] {message}")
