import time
from pathlib import Path

from dev.abhishekraha.secretmanager.config.SecretManagerConfig import (
    CLI_RELEASE_WARNING_SECONDS,
    DEFAULT_ENCRYPTED_BACKUP,
    DEFAULT_EXPORT_CSV,
    HEADER,
    SESSION_IDLE_LOCK_SECONDS,
)
from dev.abhishekraha.secretmanager.core.ReleaseUpdateService import (
    ReleaseUpdateService,
)
from dev.abhishekraha.secretmanager.core.SecretManagerService import (
    SecretManagerService,
)
from dev.abhishekraha.secretmanager.utils.Utils import (
    IdleTimeoutError,
    clear_screen,
    copy_to_clipboard,
    secure_input,
    timed_input,
    timed_secure_input,
)

SERVICE = SecretManagerService(client_name="cli")
RELEASE_UPDATE_SERVICE = ReleaseUpdateService()
BULK_INSERT_HEADER = "name,username,password,url,comments"


def _print_recovery_instructions(error):
    instructions = SERVICE.get_startup_recovery_instructions(error)
    if not instructions:
        return

    print("\nRecovery instructions:")
    for index, instruction in enumerate(instructions, start=1):
        print(f"{index}. {instruction}")


def _show_startup_release_warning():
    release_status = RELEASE_UPDATE_SERVICE.check_for_updates()
    warning_lines = RELEASE_UPDATE_SERVICE.build_cli_warning_lines(release_status)
    if not warning_lines:
        return

    print("\n".join(warning_lines))
    print(f"[WARNING] Continuing in {CLI_RELEASE_WARNING_SECONDS} second(s)...")
    time.sleep(CLI_RELEASE_WARNING_SECONDS)
    clear_screen()


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


def _prompt_for_new_secret_password():
    choice = _session_input("Press Enter to type a password or type 'g' to generate one: ").strip().lower()
    if choice == "g":
        generated_password = SERVICE.generate_password()
        print(f"Generated password: {generated_password}")
        return generated_password
    return _session_secure_input("Enter password: ")


def _prompt_for_updated_secret_password(current_password):
    choice = _session_input(
        "Press Enter to keep the current password, type 't' to enter a new one, or 'g' to generate one: "
    ).strip().lower()
    if not choice:
        return current_password
    if choice == "g":
        generated_password = SERVICE.generate_password()
        print(f"Generated password: {generated_password}")
        return generated_password
    return _session_secure_input("Enter new password: ") or current_password


def _prompt_for_backup_password():
    choice = _session_input("Press Enter to type a backup password or type 'g' to generate one: ").strip().lower()
    if choice == "g":
        generated_password = SERVICE.generate_password()
        print(f"Generated backup password: {generated_password}")
        _session_input("Press Enter after you have saved the backup password.")
        return generated_password

    backup_password = _session_secure_input("Enter backup password: ")
    confirm_password = _session_secure_input("Confirm backup password: ")
    if not backup_password:
        print("Backup password cannot be empty.")
        return None
    if backup_password != confirm_password:
        print("Backup password and confirmation do not match.")
        return None
    return backup_password


def _add_secret():
    try:
        SERVICE.add_secret(
            _session_input("Enter a name for the secret: ").strip(),
            _session_input("Enter username: "),
            _prompt_for_new_secret_password(),
            _session_input("Enter URL (optional): "),
            _session_input("Enter comments (optional): "),
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
        row = _session_input("> ")
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
    secret = SERVICE.get_secret(_session_input("Enter the name of the secret to view: ").strip())
    if not secret:
        print("Secret not found.")
        return

    SERVICE.record_secret_view(secret.get_name())
    print(secret.peak())
    user_choice = _session_input(
        "Press Enter to continue or type 'c' to copy the password to the clipboard: "
    ).strip().lower()
    if user_choice == "c":
        if copy_to_clipboard(secret.get_password()):
            SERVICE.record_secret_copy(secret.get_name())
            print("Password copied to clipboard.")
        else:
            print("Clipboard copy is not available on this system.")
        _session_input("Press Enter to continue...")
    return True


def _update_secret():
    secret = SERVICE.get_secret(_session_input("Enter the name of the secret to update: ").strip())
    if not secret:
        print("Secret not found.")
        return

    print("Leave a field blank to keep it unchanged.")
    try:
        SERVICE.update_secret(
            secret.get_name(),
            _session_input(f"Enter new name (current: {secret.get_name()}): ") or secret.get_name(),
            _session_input(f"Enter new username (current: {secret.get_username()}): ") or secret.get_username(),
            _prompt_for_updated_secret_password(secret.get_password()),
            _session_input(f"Enter new URL (current: {secret.get_url()}): ") or secret.get_url(),
            _session_input(f"Enter new comments (current: {secret.get_comments()}): ") or secret.get_comments(),
        )
    except Exception as exc:
        print(exc)
        return
    print("Secret updated successfully.")


def _delete_secret():
    try:
        SERVICE.delete_secret(_session_input("Enter the name of the secret to delete: ").strip())
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
    user_path = _session_input("Press Enter to use default or enter an alternate path: ").strip()
    target = Path(user_path) if user_path else DEFAULT_EXPORT_CSV

    while target.exists():
        print(f"Target file '{target}' already exists.")
        choice = _session_input("(o)verwrite, enter (n)ew path, or (c)ancel? [o/n/c]: ").strip().lower() or "c"
        if choice == "o":
            break
        if choice == "n":
            new_path = _session_input("Enter new export path: ").strip()
            if not new_path:
                print("No path entered. Canceling export.")
                return
            target = Path(new_path)
            continue
        print("Export cancelled.")
        return

    confirm = _session_input(f"Export will write plaintext secrets to '{target}'. Continue? (y/N): ").strip().lower()
    if confirm != "y":
        print("Export cancelled.")
        return

    try:
        SERVICE.export_secrets(target, overwrite=True)
    except Exception as exc:
        print(f"Failed to export secrets: {exc}")
        return
    print(f"Export completed: {target}")


def _export_encrypted_backup():
    print(f"Default encrypted backup path: {DEFAULT_ENCRYPTED_BACKUP}")
    user_path = _session_input("Press Enter to use default or enter an alternate path: ").strip()
    target = Path(user_path) if user_path else DEFAULT_ENCRYPTED_BACKUP

    while target.exists():
        print(f"Target file '{target}' already exists.")
        choice = _session_input("(o)verwrite, enter (n)ew path, or (c)ancel? [o/n/c]: ").strip().lower() or "c"
        if choice == "o":
            break
        if choice == "n":
            new_path = _session_input("Enter new backup path: ").strip()
            if not new_path:
                print("No path entered. Canceling backup export.")
                return
            target = Path(new_path)
            continue
        print("Backup export cancelled.")
        return

    backup_password = _prompt_for_backup_password()
    if backup_password is None:
        return

    try:
        SERVICE.export_encrypted_backup(target, backup_password, overwrite=True)
    except Exception as exc:
        print(f"Failed to export encrypted backup: {exc}")
        return
    print(f"Encrypted backup completed: {target}")


def _import_secrets():
    user_path = _session_input(
        f"Enter path to CSV or encrypted backup to import (default: {DEFAULT_EXPORT_CSV}):"
    ).strip()
    source = Path(user_path) if user_path else DEFAULT_EXPORT_CSV

    if not source.exists():
        print(f"Import file not found: {source}")
        return

    def rename_resolver(existing_name):
        print(f"Secret '{existing_name}' already exists.")
        choice = _session_input("(s)kip, (o)verwrite, (r)ename? [s/o/r]: ").strip().lower() or "s"
        if choice == "s":
            return None
        if choice == "o":
            return existing_name
        new_name = _session_input("Enter new name: ").strip()
        while not new_name or SERVICE.get_secret(new_name):
            new_name = _session_input("Name invalid or exists. Enter a different name: ").strip()
        return new_name

    try:
        import_format = SERVICE.detect_import_format(source)
        if import_format == "encrypted_backup":
            backup_password = _session_secure_input("Enter backup password: ")
            summary = SERVICE.import_encrypted_backup(
                source,
                backup_password,
                conflict_strategy="rename",
                rename_resolver=rename_resolver,
            )
        else:
            summary = SERVICE.import_secrets(source, conflict_strategy="rename", rename_resolver=rename_resolver)
    except Exception as exc:
        print(f"Failed to import secrets: {exc}")
        return

    if summary["changes_made"]:
        print("Import complete and data persisted.")
        return
    print("No changes made from import.")


def _change_master_password():
    print("You will be prompted to enter your current master password and then set a new one.")
    current_password = _session_secure_input("Enter current master password: ")
    new_password = _session_secure_input("Enter new master password: ")
    confirm_password = _session_secure_input("Confirm new master password: ")

    try:
        SERVICE.change_master_password(current_password, new_password, confirm_password)
    except Exception as exc:
        print(exc)
        return
    print("Master password changed successfully.")
    time.sleep(2)


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
    print("8. Export Encrypted Backup")
    print("9. Import Secrets (CSV / Encrypted Backup)")
    print("10. Change Master Password")
    print("11. Exit")


def _get_menu():
    return {
        "1": _add_secret,
        "2": _bulk_insert_secrets,
        "3": _view_secret,
        "4": _update_secret,
        "5": _delete_secret,
        "6": _list_secrets,
        "7": _export_secrets,
        "8": _export_encrypted_backup,
        "9": _import_secrets,
        "10": _change_master_password,
        "11": _exit_application,
    }


def _session_input(prompt):
    return timed_input(prompt, SESSION_IDLE_LOCK_SECONDS)


def _session_secure_input(prompt):
    return timed_secure_input(prompt, SESSION_IDLE_LOCK_SECONDS)


def _handle_session_idle_timeout():
    SERVICE.lock_vault()
    print(f"\nVault locked after {SESSION_IDLE_LOCK_SECONDS} second(s) of inactivity.")
    time.sleep(1)
    clear_screen()


def _run_authenticated_session():
    while True:
        try:
            _show_menu()
            user_choice = _session_input("Enter your choice: ")
            func = _get_menu().get(user_choice)

            if not func:
                print("Invalid choice. Please try again.\n")
                continue

            handled_continue_prompt = func()
            if not handled_continue_prompt:
                _session_input("Press Enter to continue...")
            clear_screen()
        except IdleTimeoutError:
            _handle_session_idle_timeout()
            return "locked"


def main():
    _show_startup_release_warning()
    try:
        if not SERVICE.initialize():
            _initial_setup()
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Startup failed: {exc}")
        _print_recovery_instructions(exc)
        return 1

    while True:
        is_authenticated = _authenticate()
        if not is_authenticated:
            return 0

        session_result = _run_authenticated_session()
        if session_result != "locked":
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
