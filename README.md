Simple Credential Manager
=========================

A minimal, local, file-backed credential manager written in Python.
It stores encrypted secrets (name, username, password, URL, comments) on the local machine and protects them with a
master password.

![SimpleCredentialManager.png](images/SimpleCredentialManager.png)
![SimpleCredentialManager1.png](images/SimpleCredentialManager1.png)

Features & Functionality
------------------------

1) First initialization
    - Interactive setup on first run prompts you to create and confirm a master password. This prepares the app for
      secure use.

2) Master password (critical)
    - The master password is the single key to the vault — keep it safe. All stored secrets are encrypted and require
      this password to access.

3) Failsafe & warnings
    - The application counts incorrect master-password attempts. It warns you when a threshold is reached and will
      perform a failsafe action (which may remove stored data) if the maximum incorrect attempts are exceeded — this is
      a security feature, not a bug.

4) Local storage
    - All data is stored locally on your machine (no cloud). You control where it runs and how data is persisted.

5) What the CLI supports (menu options)
    - Add Secret: interactively add a new secret.
    - View Secret: show details for a stored secret.
    - Update Secret: modify an existing secret.
    - Delete Secret: remove a secret from the store.
    - List All Secrets: show a list of stored secret names.
    - Exit: quit the CLI.

Installation
------------
Prerequisites:

- Python 3.8+ (Python 3.11+ tested by project artefacts)
- pip

Install dependencies:

Windows PowerShell:

    python -m pip install --upgrade pip; python -m pip install -r requirements.txt

Or use the provided Windows launcher `SimpleCredentialManagerCli.bat` which attempts to find Python and install
requirements automatically.

Usage
-----

1. Start the CLI directly:

   python SimpleCredentialManagerCli.py

2. Or use the OS-specific launcher scripts:

- Windows: run `SimpleCredentialManagerCli.bat` (this will open the CLI in a new Command Prompt window)
- POSIX: run `./SimpleCredentialManagerCli.sh`

On first run:

- You'll be prompted to create a master password and re-enter it. The app will create the metadata and secrets files on
  your local machine.
- Keep the master password safe. If you lose it, the application cannot recover the secrets (they are encrypted with a
  key derived from the password).

Container (optional Docker environment)
--------------------------------------

- The `container/` directory includes a Dockerfile that builds an Ubuntu-based image with the dependencies needed to run
  the CLI in an isolated environment. This is useful to test the project in a disposable environment before running it
  on your local machine.
- Important: by default the container does not map any host directories or volumes. Any data (secrets or metadata)
  created inside the container will be lost when the container stops or you log out, unless you explicitly mount a host
  directory or Docker volume for persistence.

To build and run the container:

    cd container
    docker build -t simple-credential-manager .
    docker run -it --rm simple-credential-manager

License
-------
This project includes a LICENSE file at the repository root. Check it for licensing details.

Contact
-------
For questions or contributions, open an issue or a pull request against the repository.
