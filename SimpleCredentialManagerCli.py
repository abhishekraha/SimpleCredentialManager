from dev.abhishekraha.secretmanager.core import SimpleCredentialManager
from dev.abhishekraha.secretmanager.utils.Utils import clear_screen

SimpleCredentialManager.initialize()
is_authenticated = SimpleCredentialManager.authenticate()

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
