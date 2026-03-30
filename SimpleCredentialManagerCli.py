import time
from pathlib import Path

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import (
    DEFAULT_EXPORT_CSV,
    HEADER,
)
from dev.abhishekraha.secretmanager.core.SecretManagerService import (
    SecretManagerService,
)
from dev.abhishekraha.secretmanager.utils.Utils import (
    clear_screen,
    copy_to_clipboard,
    secure_input,
)

SERVICE = SecretManagerService(client_name="cli")
BULK_INSERT_HEADER = "name,username,password,url,comments"


def _print_recovery_instructions(error):
    instructions = SERVICE.get_startup_recovery_instructions(error)
    if not instructions:
        return

    print("\nRecovery instructions:")
    for index, instruction in enumerate(instructions, start=1):
        print(f"{index}. {instruction}")


def _initial_setup():
    print(f"{HEADER}\n\tInitial Setup")
    while True:
        master_password = secure_input("Enter master password : ")
        validate_password = secure_input("Re-enter master password : ")
        try:
            SERVICE.setup_master_password(master_password, validate_password)
        except ValueError as exc:
            print(exc)
            continue
        break

    print("\n\n\tSetup completed.")
    print("[ NOTE ] Keep the master password handy, else all the secrets would be lost!!")
    time.sleep(5)
    clear_screen()


def _authenticate():
    print(HEADER)
    while True:
        lockout_status = SERVICE.get_lockout_status()
        if lockout_status["is_locked_out"]:
            print(f"Too many failed attempts. Try again in {lockout_status['remaining_seconds']} second(s).")
            return False

        is_authenticated, message = SERVICE.authenticate(secure_input("Enter master password: "))
        if is_authenticated:
            return True

        print(message)
        if SERVICE.get_lockout_status()["is_locked_out"] or "Vault file could not be opened:" in message:
            return False


def _add_secret():
    try:
        SERVICE.add_secret(
            input("Enter a name for the secret: ").strip(),
            input("Enter username: "),
            secure_input("Enter password: "),
            input("Enter URL (optional): "),
            input("Enter comments (optional): "),
        )
    except Exception as exc:
        print(exc)
        return
    print("Secret added successfully.")


def _bulk_insert_secrets():
    print("Bulk insert expects comma-separated values in this order:")
    print(BULK_INSERT_HEADER)
    print('Enter one row per line. Wrap values containing commas in double quotes.')
    print("Press Enter on an empty line when finished.")

    rows = []
    while True:
        row = input("> ")
        if not row:
            break
        rows.append(row)

    if not rows:
        print("Bulk insert cancelled. No rows entered.")
        return

    first_row = rows[0].strip().lower()
    payload = "\n".join(rows) if first_row == BULK_INSERT_HEADER else f"{BULK_INSERT_HEADER}\n" + "\n".join(rows)

    try:
        summary = SERVICE.bulk_insert_secrets(payload)
    except Exception as exc:
        print(exc)
        return

    print(
        "Bulk insert completed: "
        f"{summary['added']} secret(s) added, {summary['skipped_blank_rows']} blank row(s) skipped."
    )


def _view_secret():
    secret = SERVICE.get_secret(input("Enter the name of the secret to view: ").strip())
    if not secret:
        print("Secret not found.")
        return

    SERVICE.record_secret_view(secret.get_name())
    print(secret.peak())
    user_choice = input(
        "Press Enter to continue or type 'c' to copy the password to the clipboard: "
    ).strip().lower()
    if user_choice == "c":
        if copy_to_clipboard(secret.get_password()):
            SERVICE.record_secret_copy(secret.get_name())
            print("Password copied to clipboard.")
        else:
            print("Clipboard copy is not available on this system.")
        input("Press Enter to continue...")
    return True


def _update_secret():
    secret = SERVICE.get_secret(input("Enter the name of the secret to update: ").strip())
    if not secret:
        print("Secret not found.")
        return

    print("Leave a field blank to keep it unchanged.")
    try:
        SERVICE.update_secret(
            secret.get_name(),
            input(f"Enter new name (current: {secret.get_name()}): ") or secret.get_name(),
            input(f"Enter new username (current: {secret.get_username()}): ") or secret.get_username(),
            secure_input("Enter new password (leave blank to keep unchanged): ") or secret.get_password(),
            input(f"Enter new URL (current: {secret.get_url()}): ") or secret.get_url(),
            input(f"Enter new comments (current: {secret.get_comments()}): ") or secret.get_comments(),
        )
    except Exception as exc:
        print(exc)
        return
    print("Secret updated successfully.")


def _delete_secret():
    try:
        SERVICE.delete_secret(input("Enter the name of the secret to delete: ").strip())
    except Exception as exc:
        print(exc)
        return
    print("Secret deleted successfully.")


def _list_secrets():
    secret_names = SERVICE.get_secret_names()
    if not secret_names:
        print("No secrets stored.")
        return
    SERVICE.record_secret_listing(len(secret_names))
    print("Stored Secrets:")
    for name in secret_names:
        print(f"- {name}")


def _export_secrets():
    print(f"Default export path: {DEFAULT_EXPORT_CSV}")
    user_path = input("Press Enter to use default or enter an alternate path: ").strip()
    target = Path(user_path) if user_path else DEFAULT_EXPORT_CSV

    while target.exists():
        print(f"Target file '{target}' already exists.")
        choice = input("(o)verwrite, enter (n)ew path, or (c)ancel? [o/n/c]: ").strip().lower() or "c"
        if choice == "o":
            break
        if choice == "n":
            new_path = input("Enter new export path: ").strip()
            if not new_path:
                print("No path entered. Canceling export.")
                return
            target = Path(new_path)
            continue
        print("Export cancelled.")
        return

    confirm = input(f"Export will write plaintext secrets to '{target}'. Continue? (y/N): ").strip().lower()
    if confirm != "y":
        print("Export cancelled.")
        return

    try:
        SERVICE.export_secrets(target, overwrite=True)
    except Exception as exc:
        print(f"Failed to export secrets: {exc}")
        return
    print(f"Export completed: {target}")


def _import_secrets():
    user_path = input(f"Enter path to CSV to import (default: {DEFAULT_EXPORT_CSV}):").strip()
    source = Path(user_path) if user_path else DEFAULT_EXPORT_CSV

    if not source.exists():
        print(f"Import file not found: {source}")
        return

    def rename_resolver(existing_name):
        print(f"Secret '{existing_name}' already exists.")
        choice = input("(s)kip, (o)verwrite, (r)ename? [s/o/r]: ").strip().lower() or "s"
        if choice == "s":
            return None
        if choice == "o":
            return existing_name
        new_name = input("Enter new name: ").strip()
        while not new_name or SERVICE.get_secret(new_name):
            new_name = input("Name invalid or exists. Enter a different name: ").strip()
        return new_name

    try:
        summary = SERVICE.import_secrets(source, conflict_strategy="rename", rename_resolver=rename_resolver)
    except Exception as exc:
        print(f"Failed to import secrets: {exc}")
        return

    if summary["changes_made"]:
        print("Import complete and data persisted.")
        return
    print("No changes made from import.")


def _exit_application():
    SERVICE.lock_vault()
    raise SystemExit(0)


def _show_menu():
    print("\nMenu:")
    print("1. Add Secret")
    print("2. Bulk Insert Secrets")
    print("3. View Secret")
    print("4. Update Secret")
    print("5. Delete Secret")
    print("6. List All Secrets")
    print("7. Export Secrets (CSV)")
    print("8. Import Secrets (CSV)")
    print("9. Exit")


def _get_menu():
    return {
        "1": _add_secret,
        "2": _bulk_insert_secrets,
        "3": _view_secret,
        "4": _update_secret,
        "5": _delete_secret,
        "6": _list_secrets,
        "7": _export_secrets,
        "8": _import_secrets,
        "9": _exit_application,
    }


def main():
    try:
        if not SERVICE.initialize():
            _initial_setup()
        is_authenticated = _authenticate()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Startup failed: {exc}")
        _print_recovery_instructions(exc)
        return 1

    if not is_authenticated:
        return 0

    while True:
        _show_menu()
        user_choice = input("Enter your choice: ")
        func = _get_menu().get(user_choice)

        if not func:
            print("Invalid choice. Please try again.\n")
            continue

        handled_continue_prompt = func()
        if not handled_continue_prompt:
            input("Press Enter to continue...")
        clear_screen()


if __name__ == "__main__":
    raise SystemExit(main())
