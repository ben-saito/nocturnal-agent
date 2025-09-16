"""Command line interface for Nocturnal Agent."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from nocturnal_agent.core.config import ConfigManager, create_default_config, load_config


console = Console()


@click.group()
@click.option('--config', '-c', help='Configuration file path')
@click.option('--debug', is_flag=True, help='Enable debug mode')
@click.pass_context
def main(ctx: click.Context, config: Optional[str], debug: bool) -> None:
    """Nocturnal Agent - Autonomous night development system."""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config
    ctx.obj['debug'] = debug


@main.command()
@click.option('--output', '-o', default='config/nocturnal-agent.yaml',
              help='Output path for configuration file')
def init(output: str) -> None:
    """Initialize Nocturnal Agent with default configuration."""
    try:
        create_default_config(output)
        console.print(f"✅ Configuration file created at: {output}", style="green")
        console.print("Edit the configuration file to customize settings.", style="yellow")
    except Exception as e:
        console.print(f"❌ Failed to create configuration: {e}", style="red")
        sys.exit(1)


@main.command()
@click.pass_context
def config_check(ctx: click.Context) -> None:
    """Check configuration validity."""
    try:
        config = load_config(ctx.obj.get('config_path'))
        console.print("✅ Configuration is valid", style="green")
        
        # Display configuration summary
        table = Table(title="Configuration Summary")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="magenta")
        
        table.add_row("Project Name", config.project_name)
        table.add_row("Working Directory", config.working_directory)
        table.add_row("Quality Threshold", f"{config.quality.overall_threshold:.2f}")
        table.add_row("Night Window", f"{config.scheduler.start_time} - {config.scheduler.end_time}")
        table.add_row("Max Changes/Night", str(config.scheduler.max_changes_per_night))
        table.add_row("Local LLM Enabled", "✅" if config.llm.enabled else "❌")
        table.add_row("Claude Enabled", "✅" if config.agents.claude.enabled else "❌")
        table.add_row("Monthly Budget", f"${config.cost.monthly_budget_usd:.2f}")
        
        console.print(table)
        
    except Exception as e:
        console.print(f"❌ Configuration error: {e}", style="red")
        sys.exit(1)


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show current system status."""
    try:
        config = load_config(ctx.obj.get('config_path'))
        
        table = Table(title="Nocturnal Agent Status")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Details", style="yellow")
        
        # Check LLM availability
        table.add_row("Local LLM", "⚠️ Not Checked", f"URL: {config.llm.api_url}")
        
        # Check Claude CLI
        table.add_row("Claude CLI", "⚠️ Not Checked", "Command: claude")
        
        # Check working directory
        working_dir = Path(config.working_directory)
        if working_dir.exists():
            table.add_row("Working Directory", "✅ Available", str(working_dir.absolute()))
        else:
            table.add_row("Working Directory", "❌ Missing", str(working_dir.absolute()))
        
        # Check Obsidian vault
        vault_path = Path(config.obsidian.vault_path)
        if vault_path.exists():
            table.add_row("Knowledge Vault", "✅ Available", str(vault_path.absolute()))
        else:
            table.add_row("Knowledge Vault", "⚠️ Will Create", str(vault_path.absolute()))
        
        console.print(table)
        
    except Exception as e:
        console.print(f"❌ Status check failed: {e}", style="red")
        sys.exit(1)


@main.command()
@click.option('--task', '-t', help='Task description to execute')
@click.option('--priority', '-p', type=click.Choice(['low', 'medium', 'high', 'critical']),
              default='medium', help='Task priority')
@click.pass_context
def add_task(ctx: click.Context, task: Optional[str], priority: str) -> None:
    """Add a task to the execution queue."""
    if not task:
        task = click.prompt("Enter task description")
    
    console.print(f"📝 Task added: {task}", style="green")
    console.print(f"Priority: {priority}", style="yellow")
    console.print("⚠️ Task execution not implemented yet", style="red")


@main.command()
@click.option('--dry-run', is_flag=True, help='Simulate night execution without making changes')
@click.pass_context
def night_run(ctx: click.Context, dry_run: bool) -> None:
    """Start night execution (for testing purposes)."""
    try:
        config = load_config(ctx.obj.get('config_path'))
        
        if dry_run:
            console.print("🌙 Starting night execution (DRY RUN)", style="blue")
        else:
            console.print("🌙 Starting night execution", style="blue")
        
        console.print("⚠️ Night execution not implemented yet", style="red")
        console.print("Current configuration loaded successfully", style="green")
        
    except Exception as e:
        console.print(f"❌ Failed to start night execution: {e}", style="red")
        sys.exit(1)


@main.command()
def version() -> None:
    """Show version information."""
    from nocturnal_agent import __version__
    console.print(f"Nocturnal Agent v{__version__}", style="green")


if __name__ == "__main__":
    main()