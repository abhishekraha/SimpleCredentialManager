from dev.abhishekraha.secretmanager.core import SimpleCredentialManager

SimpleCredentialManager.initialize()
is_authenticated = SimpleCredentialManager.authenticate()

if is_authenticated:
    print("Authenticated")
else:
    print("Not Authenticated")
