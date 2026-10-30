import json
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is in sys.path when invoked directly
_project_root = str(Path(__file__).resolve().parents[4])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import (
    APP_NAME,
    APP_VERSION,
)
from dev.abhishekraha.secretmanager.core.PasswordHealthService import PasswordHealthService
from dev.abhishekraha.secretmanager.core.SecretManagerService import SecretManagerService
from dev.abhishekraha.secretmanager.core.TotpService import TotpService
from dev.abhishekraha.secretmanager.utils.SecureClipboardManager import SecureClipboardManager

# Typer app initialization
app = typer.Typer(
    name="scm",
    help=f"{APP_NAME} ({APP_VERSION}) — Modern, secure credential manager CLI.",
    no_args_is_help=False,
    invoke_without_command=True,
)

console = Console()
err_console = Console(stderr=True)


def _get_service(client_name: str = "modern_cli") -> SecretManagerService:
    service = SecretManagerService(client_name=client_name)
    return service


def _prompt_and_authenticate(service: SecretManagerService, max_attempts: int = 3) -> bool:
    """Prompt the user for master password until authenticated or aborted."""
    if not service.is_initialized():
        console.print("[bold yellow]Vault is not initialized.[/bold yellow] Running initial setup...")
        while True:
            pwd = typer.prompt("Create Master Password", hide_input=True)
            if not pwd:
                console.print("[bold red]Master password cannot be empty.[/bold red]")
                continue
            confirm_pwd = typer.prompt("Confirm Master Password", hide_input=True)
            if pwd != confirm_pwd:
                console.print("[bold red]Passwords do not match. Please try again.[/bold red]")
                continue
            try:
                service.setup_master_password(pwd, confirm_pwd)
                console.print("[bold green]Vault initialized successfully![/bold green]")
                # Authenticate immediately
                service.authenticate(pwd)
                return True
            except Exception as exc:
                console.print(f"[bold red]Initialization failed: {exc}[/bold red]")
                return False

    service.initialize()
    lockout_status = service.get_lockout_status()
    if lockout_status.get("is_locked_out"):
        rem = lockout_status.get("remaining_seconds", 0)
        console.print(f"[bold red]Vault is currently locked out. Please wait {rem} second(s).[/bold red]")
        return False

    attempts = 0
    while attempts < max_attempts:
        pwd = typer.prompt("Master Password", hide_input=True)
        success, message = service.authenticate(pwd)
        if success:
            return True
        console.print(f"[bold red]{message}[/bold red]")
        attempts += 1
        lockout = service.get_lockout_status()
        if lockout.get("is_locked_out") or lockout.get("failed_attempts", 0) >= 3 or attempts >= max_attempts:
            wipe = typer.confirm("You have exceeded maximum attempts. Wipe credentials and start fresh?", default=False)
            if wipe:
                confirm = typer.prompt("Type 'WIPE' to confirm permanent deletion")
                if confirm.strip() == "WIPE":
                    service.reset_vault_and_wipe_all()
                    console.print("[bold green]Vault has been wiped. Initializing fresh vault...[/bold green]")
                    return _prompt_and_authenticate(service, max_attempts=max_attempts)
            if lockout.get("is_locked_out"):
                return False

    return False


@app.callback()
def main_callback(ctx: typer.Context):
    """
    Callback handling default invocation: if no subcommand is passed, seamlessly
    launches interactive menu mode.
    """
    if ctx.invoked_subcommand is None:
        interactive()


@app.command("interactive", help="Launch the full interactive terminal menu interface.")
def interactive():
    """Seamlessly launches interactive menu mode."""
    import SimpleCredentialManagerCli
    SimpleCredentialManagerCli.run_legacy_cli()


@app.command("list", help="List stored credentials in a styled Rich Table.")
def list_credentials(
    filter_text: Optional[str] = typer.Option(
        None, "--filter", "-f", help="Case-insensitive text filter for credentials."
    ),
    category_filter: Optional[str] = typer.Option(
        None, "--category", "-c", help="Filter by category (e.g. login, api_key, server)."
    ),
):
    """Displays credentials in a styled Rich Table with status, category, updated date, and --filter option."""
    service = _get_service()
    if not _prompt_and_authenticate(service):
        raise typer.Exit(code=1)

    records = service.get_secret_records(filter_text=filter_text or "")
    if category_filter:
        cat_lower = category_filter.strip().lower()
        records = [r for r in records if (r.get_category() or "login").lower() == cat_lower]

    if not records:
        if filter_text or category_filter:
            console.print("[yellow]No credentials found matching your criteria.[/yellow]")
        else:
            console.print("[yellow]Vault is empty. Add a secret using 'scm add <name>'.[/yellow]")
        return

    table = Table(
        title=f"Stored Credentials ({len(records)})",
        box=box.ROUNDED,
        header_style="bold cyan",
        title_style="bold magenta",
    )
    table.add_column("Name", style="bold white")
    table.add_column("Username", style="green")
    table.add_column("Category", style="yellow")
    table.add_column("2FA / TOTP", style="cyan", justify="center")
    table.add_column("Last Updated", style="dim")
    table.add_column("Tags", style="blue")

    for sec in records:
        has_totp = "✓" if getattr(sec, "get_totp_secret", lambda: None)() else "-"
        upd = sec.get_update_date() or sec.get_create_date()
        upd_str = upd.strftime("%Y-%m-%d %H:%M") if upd else "-"
        tags = sec.get_tags() if hasattr(sec, "get_tags") else []
        tags_str = ", ".join(tags) if tags else "-"
        category = sec.get_category() if hasattr(sec, "get_category") else "login"

        table.add_row(
            sec.get_name(),
            sec.get_username() or "-",
            category or "login",
            has_totp,
            upd_str,
            tags_str,
        )

    console.print(table)


@app.command("get", help="Retrieve credentials for a specific item.")
def get_secret(
    name: str = typer.Argument(..., help="Exact name of the secret to retrieve."),
    clip: bool = typer.Option(
        False, "--clip", "-c", help="Securely copy password to clipboard with 30s auto-clear."
    ),
    show: bool = typer.Option(
        False, "--show", "-s", help="Display the plaintext password on screen."
    ),
    as_json: bool = typer.Option(
        False, "--json", "-j", help="Output JSON payload for automation and scripting."
    ),
):
    """
    Get secret options:
    --clip: copies password with auto-clear
    --show: displays password
    --json: prints JSON payload for automation
    """
    service = _get_service()
    if not _prompt_and_authenticate(service):
        raise typer.Exit(code=1)

    secret = service.get_secret(name)
    if not secret:
        err_console.print(f"[bold red]Secret '{name}' not found.[/bold red]")
        raise typer.Exit(code=1)

    # If --json requested
    if as_json:
        payload = secret.to_dict() if hasattr(secret, "to_dict") else {
            "name": secret.get_name(),
            "username": secret.get_username(),
            "password": secret.get_password(),
            "url": secret.get_url(),
            "comments": secret.get_comments(),
        }
        # Print pure json to stdout
        console.print(json.dumps(payload, indent=2))
        return

    # Handle --clip option
    if clip:
        pwd = secret.get_password()
        copied = SecureClipboardManager.copy(pwd, clear_timeout_seconds=30)
        if copied:
            console.print(f"[bold green]✓ Password for '{name}' copied to clipboard (auto-clears in 30s).[/bold green]")
        else:
            err_console.print("[bold red]Failed to copy to clipboard.[/bold red]")

    # Styled detail panel
    table = Table(show_header=False, box=box.SIMPLE)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")

    table.add_row("Name", secret.get_name())
    table.add_row("Username", secret.get_username() or "-")

    if show:
        table.add_row("Password", f"[bold green]{secret.get_password()}[/bold green]")
    else:
        table.add_row("Password", "[dim]******** (use --show or --clip)[/dim]")

    if secret.get_url():
        table.add_row("URL", secret.get_url())
    if secret.get_comments():
        table.add_row("Comments", secret.get_comments())

    if hasattr(secret, "get_category") and secret.get_category():
        table.add_row("Category", secret.get_category())
    if hasattr(secret, "get_tags") and secret.get_tags():
        table.add_row("Tags", ", ".join(secret.get_tags()))

    panel = Panel(
        table,
        title=f"Credential: [bold]{name}[/bold]",
        border_style="cyan",
        expand=False,
    )
    console.print(panel)


@app.command("add", help="Add a new credential to the vault.")
def add_secret(
    name: str = typer.Argument(..., help="Unique identifier/name for the credential."),
    username: Optional[str] = typer.Option(
        None, "--username", "-u", help="Username or login email."
    ),
    password: Optional[str] = typer.Option(
        None, "--password", "-p", help="Plaintext password (prompted if omitted)."
    ),
    generate: bool = typer.Option(
        False, "--generate", "-g", help="Generate a cryptographically secure random password."
    ),
    url: Optional[str] = typer.Option(
        "", "--url", help="Associated service or login URL."
    ),
    comments: Optional[str] = typer.Option(
        "", "--comments", help="Optional notes or comments."
    ),
    category: str = typer.Option(
        "login", "--category", help="Category: login, api_key, server, secure_note, etc."
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t", help="Comma-separated list of tags (e.g. 'work,aws,prod')."
    ),
    totp_secret: Optional[str] = typer.Option(
        None, "--totp", help="Optional TOTP Base32 secret key or otpauth:// URI."
    ),
):
    """
    Options:
    --username, --password, --generate, --category, --tags, --totp
    """
    service = _get_service()
    if not _prompt_and_authenticate(service):
        raise typer.Exit(code=1)

    # Check existence
    if service.get_secret(name):
        err_console.print(f"[bold red]A secret named '{name}' already exists.[/bold red]")
        raise typer.Exit(code=1)

    final_username = username
    if final_username is None:
        final_username = typer.prompt("Username (optional)", default="", show_default=False)

    final_password = password
    if generate:
        final_password = service.generate_password()
        console.print(f"[bold green]Generated password:[/bold green] {final_password}")
    elif final_password is None:
        final_password = typer.prompt("Password", hide_input=True)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    parsed_totp = None
    if totp_secret:
        try:
            parsed_totp = TotpService.parse_secret(totp_secret)
        except ValueError as exc:
            err_console.print(f"[bold red]Invalid TOTP secret: {exc}[/bold red]")
            raise typer.Exit(code=1)

    try:
        service.add_secret(
            name=name,
            username=final_username,
            password=final_password,
            url=url or "",
            comments=comments or "",
            category=category,
            totp_secret=parsed_totp,
            tags=tag_list,
        )
        console.print(f"[bold green]✓ Successfully added credential '{name}'.[/bold green]")
    except Exception as exc:
        err_console.print(f"[bold red]Failed to add credential: {exc}[/bold red]")
        raise typer.Exit(code=1)


@app.command("totp", help="Display live 2FA / TOTP authentication code.")
def totp_code(
    name: str = typer.Argument(..., help="Name of the credential containing TOTP secret."),
    clip: bool = typer.Option(
        False, "--clip", "-c", help="Copy the current 6-digit TOTP code to clipboard."
    ),
):
    """Displays live 2FA code with remaining seconds and --clip option."""
    service = _get_service()
    if not _prompt_and_authenticate(service):
        raise typer.Exit(code=1)

    secret = service.get_secret(name)
    if not secret:
        err_console.print(f"[bold red]Secret '{name}' not found.[/bold red]")
        raise typer.Exit(code=1)

    totp_secret = getattr(secret, "get_totp_secret", lambda: None)()
    if not totp_secret:
        err_console.print(f"[bold red]No TOTP 2FA secret configured for '{name}'.[/bold red]")
        raise typer.Exit(code=1)

    try:
        totp_info = TotpService.generate_totp(totp_secret)
        code = totp_info["code"]
        remaining = totp_info["remaining_seconds"]
    except Exception as exc:
        err_console.print(f"[bold red]Failed to generate TOTP code: {exc}[/bold red]")
        raise typer.Exit(code=1)

    # Style code with color based on remaining seconds
    rem_color = "green" if remaining > 10 else "yellow" if remaining > 5 else "red"

    panel_content = (
        f"[bold white on blue]  {code[:3]} {code[3:]}  [/bold white on blue]\n\n"
        f"Valid for: [{rem_color} bold]{remaining}s[/{rem_color} bold]"
    )
    console.print(Panel(panel_content, title=f"2FA Code: {name}", border_style="blue", expand=False))

    if clip:
        SecureClipboardManager.copy(code, clear_timeout_seconds=remaining)
        console.print(f"[bold green]✓ TOTP code '{code}' copied to clipboard (valid for {remaining}s).[/bold green]")


@app.command("health", help="Run vault security & password health audit.")
def health_audit(
    check_breaches: bool = typer.Option(
        False, "--breaches", "-b", help="Check passwords against HaveIBeenPwned k-anonymity API."
    ),
):
    """Runs PasswordHealthService and displays color-coded health summary (score, weak count, duplicates)."""
    service = _get_service()
    if not _prompt_and_authenticate(service):
        raise typer.Exit(code=1)

    records = service.get_secret_records()
    if not records:
        console.print("[yellow]Vault is empty. Add credentials to evaluate health.[/yellow]")
        return

    with console.status("[bold green]Analyzing vault password health...[/bold green]"):
        report = PasswordHealthService.audit_vault(records, check_breaches=check_breaches)

    score = report.get("health_score", 0)
    score_color = "green" if score >= 80 else "yellow" if score >= 50 else "red"

    summary_table = Table(title="Vault Security Health Score", box=box.ROUNDED, show_header=False)
    summary_table.add_column("Metric", style="bold cyan")
    summary_table.add_column("Value")

    summary_table.add_row("Overall Health Score", f"[{score_color} bold]{score} / 100[/{score_color} bold]")
    summary_table.add_row("Total Credentials", str(report.get("total_secrets", 0)))
    summary_table.add_row("Weak Passwords", f"[{'red' if report['weak_secrets'] else 'green'}]{len(report['weak_secrets'])}[/{'red' if report['weak_secrets'] else 'green'}]")
    summary_table.add_row("Reused Passwords", f"[{'red' if report['reused_secrets'] else 'green'}]{len(report['reused_secrets'])} groups[/{'red' if report['reused_secrets'] else 'green'}]")
    summary_table.add_row("Stale (>365d)", str(len(report.get("stale_secrets", []))))

    if check_breaches:
        summary_table.add_row("Breached (HIBP)", f"[{'red' if report['breached_secrets'] else 'green'}]{len(report['breached_secrets'])}[/{'red' if report['breached_secrets'] else 'green'}]")

    console.print(summary_table)

    # Detailed weak list
    if report["weak_secrets"]:
        console.print("\n[bold red]Weak Passwords:[/bold red]")
        weak_table = Table(box=box.SIMPLE_HEAD)
        weak_table.add_column("Name", style="bold")
        weak_table.add_column("Username")
        weak_table.add_column("Entropy (bits)", justify="right")
        weak_table.add_column("Issue", style="yellow")
        for w in report["weak_secrets"]:
            weak_table.add_row(w["name"], w["username"] or "-", f"{w['entropy']:.1f}", w["reason"])
        console.print(weak_table)

    # Detailed reused list
    if report["reused_secrets"]:
        console.print("\n[bold red]Duplicate / Reused Passwords:[/bold red]")
        reused_table = Table(box=box.SIMPLE_HEAD)
        reused_table.add_column("Accounts Reusing Password")
        reused_table.add_column("Count", justify="center")
        for r in report["reused_secrets"]:
            reused_table.add_row(", ".join(r["secret_names"]), str(r["count"]))
        console.print(reused_table)


def main():
    """CLI entry point for package and scripts."""
    app()


if __name__ == "__main__":
    main()
