from datetime import datetime

from dev.abhishekraha.secretmanager.utils.Utils import secure_input


def create_secret(secret_name):
    username = input("Enter username: ")
    password = secure_input("Enter password: ")
    url = input("Enter URL (optional): ")
    comments = input("Enter comments (optional): ")
    return Secret(secret_name, username, password, url, comments)


class Secret:
    def __init__(
        self,
        name,
        username,
        password,
        url="",
        comments="",
        create_date=None,
        update_date=None,
        tags=None,
        category="login",
        favorite=False,
        totp_secret="",
        is_favorite=None,
    ):
        self._name = name
        self._username = username
        self._password = password
        self._url = url or ""
        self._comments = comments or ""
        self._create_date = create_date or datetime.now()
        self._update_date = update_date
        self._tags = list(tags) if tags else []
        self._category = category or "login"
        if is_favorite is not None:
            self._favorite = bool(is_favorite)
        else:
            self._favorite = bool(favorite)
        self._totp_secret = totp_secret or ""

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

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value):
        self._username = value

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, value):
        self._password = value

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, value):
        self._url = value

    @property
    def comments(self):
        return self._comments

    @comments.setter
    def comments(self, value):
        self._comments = value

    @property
    def category(self):
        return self._category

    @category.setter
    def category(self, value):
        self._category = value

    @property
    def favorite(self):
        return self._favorite

    @favorite.setter
    def favorite(self, value):
        self._favorite = bool(value)

    @property
    def totp_secret(self):
        return self._totp_secret

    @totp_secret.setter
    def totp_secret(self, value):
        self._totp_secret = value

    @property
    def tags(self):
        return list(self._tags)

    @tags.setter
    def tags(self, value):
        self._tags = list(value) if value else []

    @property
    def create_date(self):
        return self._create_date

    @property
    def update_date(self):
        return self._update_date

    def has_totp(self):
        return bool(self._totp_secret and str(self._totp_secret).strip())


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

    def get_tags(self):
        return list(self._tags)

    def set_tags(self, tags):
        self._tags = list(tags) if tags else []

    def get_category(self):
        return self._category

    def set_category(self, category):
        self._category = category or "login"

    def is_favorite(self):
        return self._favorite

    def get_favorite(self):
        return self._favorite

    def set_favorite(self, favorite):
        self._favorite = bool(favorite)

    def get_totp_secret(self):
        return self._totp_secret

    def set_totp_secret(self, totp_secret):
        self._totp_secret = totp_secret or ""

    def to_dict(self):
        return {
            "name": self._name,
            "username": self._username,
            "password": self._password,
            "url": self._url,
            "comments": self._comments,
            "created_at": self._create_date.isoformat(),
            "updated_at": self._update_date.isoformat() if self._update_date else None,
            "tags": list(self._tags),
            "category": self._category,
            "favorite": self._favorite,
            "is_favorite": self._favorite,
            "totp_secret": self._totp_secret,
        }

    @classmethod
    def from_dict(cls, secret_payload):
        # Support both 'favorite' and 'is_favorite' for backward compatibility
        favorite_val = secret_payload.get("favorite")
        if favorite_val is None:
            favorite_val = secret_payload.get("is_favorite", False)
        return cls(
            name=secret_payload.get("name", ""),
            username=secret_payload.get("username", ""),
            password=secret_payload.get("password", ""),
            url=secret_payload.get("url", ""),
            comments=secret_payload.get("comments", ""),
            create_date=_parse_datetime(secret_payload.get("created_at")),
            update_date=_parse_datetime(secret_payload.get("updated_at")),
            tags=secret_payload.get("tags") or [],
            category=secret_payload.get("category", "login"),
            favorite=bool(favorite_val),
            totp_secret=secret_payload.get("totp_secret") or "",
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
