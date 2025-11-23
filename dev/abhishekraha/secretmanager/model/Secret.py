from datetime import datetime

from dev.abhishekraha.secretmanager.codec import CodecUtils
from dev.abhishekraha.secretmanager.utils.Utils import secure_input


def create_secret(secret_name):
    username = input("Enter username: ")
    password = CodecUtils.encrypt_password(secure_input("Enter password: "))
    url = input("Enter URL (optional): ")
    comments = input("Enter comments (optional): ")
    return Secret(secret_name, username, password, url, comments)


class Secret:
    def __init__(self, name, username, password, url, comments):
        self._name = name
        self._username = username
        self._password = password
        self._url = url
        self._comments = comments
        self._create_date = datetime.now()
        self._update_date = None

    def set_name(self, name):
        self._name = name

    def get_name(self):
        return self._name

    def set_username(self, username):
        self._username = username

    def get_username(self):
        return self._username

    def set_password(self, plain_text_password):
        self._password = CodecUtils.encrypt_password(plain_text_password)

    def get_password(self):
        return CodecUtils.decrypt_password(self._password)

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
