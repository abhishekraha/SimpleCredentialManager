import argparse
import re
import tarfile
import zipfile
from pathlib import Path


COMMON_PATHS = [
    "CHANGELOG.md",
    "LICENSE",
    "README.md",
    "requirements.txt",
    "SimpleCredentialManagerCli.py",
    "SimpleCredentialManagerUi.py",
    "dev",
]

PACKAGE_DEFINITIONS = {
    "windows": {
        "archive_kind": "zip",
        "launcher_paths": [
            "SimpleCredentialManagerCli.bat",
            "SimpleCredentialManagerUi.bat",
        ],
    },
    "linux": {
        "archive_kind": "tar.gz",
        "launcher_paths": [
            "SimpleCredentialManagerCli.sh",
            "SimpleCredentialManagerUi.sh",
        ],
    },
    "macos": {
        "archive_kind": "tar.gz",
        "launcher_paths": [
            "SimpleCredentialManagerCli.sh",
            "SimpleCredentialManagerUi.sh",
        ],
    },
}

SKIPPED_DIRECTORY_NAMES = {
    "__pycache__",
    ".git",
    ".github",
    ".idea",
    ".venv",
    "venv",
    "tests",
    "container",
    "images",
}
SKIPPED_FILE_SUFFIXES = {".pyc", ".pyo"}
EXECUTABLE_SUFFIXES = {".sh"}


def main():
    parser = argparse.ArgumentParser(
        description="Build platform-specific release archives for Simple Credential Manager."
    )
    parser.add_argument(
        "--version",
        help="Version number without a leading v. Defaults to APP_VERSION in SecretManagerConfig.py.",
    )
    parser.add_argument(
        "--dist-dir",
        help="Output directory for generated archives. Defaults to ./dist.",
    )
    args = parser.parse_args()

    repository_root = Path(__file__).resolve().parents[2]
    version = args.version or _load_version(repository_root)
    dist_directory = Path(args.dist_dir) if args.dist_dir else repository_root / "dist"
    dist_directory.mkdir(parents=True, exist_ok=True)

    for existing_archive in dist_directory.glob("simple-credential-manager-*"):
        if existing_archive.is_file():
            existing_archive.unlink()

    source_entries = _collect_source_entries(repository_root)
    for platform_name, package_definition in PACKAGE_DEFINITIONS.items():
        archive_path = _build_archive(
            repository_root=repository_root,
            dist_directory=dist_directory,
            version=version,
            platform_name=platform_name,
            archive_kind=package_definition["archive_kind"],
            source_entries=source_entries + package_definition["launcher_paths"],
        )
        print(archive_path.relative_to(repository_root))


def _load_version(repository_root):
    config_path = repository_root / "dev" / "abhishekraha" / "secretmanager" / "config" / "SecretManagerConfig.py"
    config_text = config_path.read_text(encoding="utf-8")
    version_match = re.search(r'APP_VERSION\s*=\s*"v?([^"]+)"', config_text)
    if not version_match:
        raise SystemExit("APP_VERSION was not found in SecretManagerConfig.py")
    return version_match.group(1)


def _collect_source_entries(repository_root):
    resolved_entries = []
    for relative_path in COMMON_PATHS:
        source_path = repository_root / relative_path
        if not source_path.exists():
            raise SystemExit(f"Expected release source path was not found: {relative_path}")
        resolved_entries.append(relative_path)
    return resolved_entries


def _build_archive(repository_root, dist_directory, version, platform_name, archive_kind, source_entries):
    package_root_name = f"SimpleCredentialManager-v{version}-{platform_name}"
    archive_stem = f"simple-credential-manager-v{version}-{platform_name}"

    if archive_kind == "zip":
        archive_path = dist_directory / f"{archive_stem}.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for relative_path in source_entries:
                _write_zip_entry(
                    archive=archive,
                    repository_root=repository_root,
                    source_path=repository_root / relative_path,
                    archive_root=package_root_name,
                )
        return archive_path

    archive_path = dist_directory / f"{archive_stem}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        for relative_path in source_entries:
            _write_tar_entry(
                archive=archive,
                repository_root=repository_root,
                source_path=repository_root / relative_path,
                archive_root=package_root_name,
            )
    return archive_path


def _write_zip_entry(archive, repository_root, source_path, archive_root):
    if source_path.is_dir():
        for child_path in sorted(source_path.rglob("*")):
            if _should_skip_path(child_path, repository_root):
                continue
            if child_path.is_dir():
                continue
            archive_path = Path(archive_root) / child_path.relative_to(repository_root)
            archive.write(child_path, archive_path.as_posix())
        return

    if _should_skip_path(source_path, repository_root):
        return
    archive_path = Path(archive_root) / source_path.relative_to(repository_root)
    archive.write(source_path, archive_path.as_posix())


def _write_tar_entry(archive, repository_root, source_path, archive_root):
    if source_path.is_dir():
        for child_path in sorted(source_path.rglob("*")):
            if _should_skip_path(child_path, repository_root):
                continue
            archive_path = Path(archive_root) / child_path.relative_to(repository_root)
            tar_info = archive.gettarinfo(str(child_path), archive_path.as_posix())
            if child_path.is_dir():
                tar_info.mode = 0o755
                archive.addfile(tar_info)
                continue
            tar_info.mode = 0o755 if child_path.suffix in EXECUTABLE_SUFFIXES else 0o644
            with child_path.open("rb") as source_file:
                archive.addfile(tar_info, source_file)
        return

    if _should_skip_path(source_path, repository_root):
        return
    archive_path = Path(archive_root) / source_path.relative_to(repository_root)
    tar_info = archive.gettarinfo(str(source_path), archive_path.as_posix())
    tar_info.mode = 0o755 if source_path.suffix in EXECUTABLE_SUFFIXES else 0o644
    with source_path.open("rb") as source_file:
        archive.addfile(tar_info, source_file)


def _should_skip_path(path, repository_root):
    relative_parts = path.relative_to(repository_root).parts
    if any(part in SKIPPED_DIRECTORY_NAMES for part in relative_parts):
        return True
    if path.suffix in SKIPPED_FILE_SUFFIXES:
        return True
    return False


if __name__ == "__main__":
    main()
