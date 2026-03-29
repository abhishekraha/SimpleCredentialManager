from datetime import datetime

from dev.abhishekraha.secretmanager.utils.Utils import secure_input


def create_secret(secret_name):
    username = input("Enter username: ")
    password = secure_input("Enter password: ")
    url = input("Enter URL (optional): ")
    comments = input("Enter comments (optional): ")
    return Secret(secret_name, username, password, url, comments)


class Secret:
    def __init__(self, name, username, password, url, comments, create_date=None, update_date=None):
        self._name = name
        self._username = username
        self._password = password
        self._url = url
        self._comments = comments
        self._create_date = create_date or datetime.now()
        self._update_date = update_date

    def set_name(self, name):
        self._name = name

    def get_name(self):
        return self._name

    def set_username(self, username):
        self._username = username

    def get_username(self):
        return self._username

    def set_password(self, plain_text_password):
        self._password = plain_text_password

    def get_password(self):
        return self._password

    def set_url(self, url):
        self._url = url

    def get_url(self):
        return self._url

    def set_comments(self, comments):
        self._comments = comments

    def get_comments(self):
        return self._comments

    def get_create_date(self):
        return self._create_date

    def get_update_date(self):
        return self._update_date

    def set_update_date(self, update_date):
        self._update_date = update_date

    def to_dict(self):
        return {
            "name": self._name,
            "username": self._username,
            "password": self._password,
            "url": self._url,
            "comments": self._comments,
            "created_at": self._create_date.isoformat(),
            "updated_at": self._update_date.isoformat() if self._update_date else None,
        }

    @classmethod
    def from_dict(cls, secret_payload):
        return cls(
            secret_payload.get("name", ""),
            secret_payload.get("username", ""),
            secret_payload.get("password", ""),
            secret_payload.get("url", ""),
            secret_payload.get("comments", ""),
            create_date=_parse_datetime(secret_payload.get("created_at")),
            update_date=_parse_datetime(secret_payload.get("updated_at")),
        )

    def peak(self):
        return f"""
        Name: {self.get_name()}
        Username: {self.get_username()}
        Password: {self.get_password()}
        URL: {self.get_url()}
        Comments: {self.get_comments()}
        Date Created: {self.get_create_date()}
        Date Updated: {self.get_update_date()}
        """


def _parse_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)
