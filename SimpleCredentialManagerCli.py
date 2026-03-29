from dev.abhishekraha.secretmanager.config.SecretManagerConfig import DEFAULT_EXPORT_CSV, SECRET_FILE, \
    SECRET_MANAGER_META_DATA
from dev.abhishekraha.secretmanager.core import SimpleCredentialManager
from dev.abhishekraha.secretmanager.utils.Utils import clear_screen


def _print_recovery_instructions(error):
    error_message = str(error)
    if "unsupported legacy format" not in error_message:
        return

    print("\nRecovery instructions:")
    print(f"1. Back up the metadata file: {SECRET_MANAGER_META_DATA}")

    if SECRET_FILE.exists():
        print(f"2. A legacy vault file exists at {SECRET_FILE}.")
        print("   Stop here and migrate that vault before deleting anything.")
        print("   The current code does not auto-convert the old vault format yet.")
        return

    print(f"2. No vault file was found at {SECRET_FILE}.")
    if DEFAULT_EXPORT_CSV.exists():
        print(f"3. A CSV export is available at {DEFAULT_EXPORT_CSV}. Keep this file safe.")
        print(f"4. Rename or delete the legacy metadata file: {SECRET_MANAGER_META_DATA}")
        print("5. Run the app again and create a new master password.")
        print("6. Use 'Import Secrets (CSV)' and select the CSV export file to restore your entries.")
    else:
        print(f"3. Rename or delete the legacy metadata file: {SECRET_MANAGER_META_DATA}")
        print("4. Run the app again and create a new master password.")
        print("5. Re-enter your secrets manually, because no importable backup was found.")


try:
    SimpleCredentialManager.initialize()
    is_authenticated = SimpleCredentialManager.authenticate()
except (FileNotFoundError, ValueError) as exc:
    print(f"Startup failed: {exc}")
    _print_recovery_instructions(exc)
    raise SystemExit(1)

if not is_authenticated:
    exit()

while True:
    SimpleCredentialManager.show_menu()
    user_choice = input("Enter your choice: ")

    func = SimpleCredentialManager.get_menu().get(user_choice)

    if func:
        func()
        input("Press Enter to continue...")
        clear_screen()
    else:
        print("Invalid choice. Please try again.\n")
