from datetime import datetime


class Secret:
    def __init__(self, name, username, password, url, comments):
        self._name = name
        self._username = username
        self._password = password
        self._url = url
        self._comments = comments
        self._create_date = datetime.now()

    def set_name(self, name):
        self._name = name

    def get_name(self):
        return self._name

    def set_username(self, username):
        self._username = username

    def get_username(self):
        return self._username

    def set_password(self, password):
        self._password = password

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

    def peak(self):
        return f"""
        Name: {self._name}
        Username: {self._username}
        Password: {self._password}
        URL: {self._url}
        Comments: {self._comments}
        Date Created: {self._create_date}
        """
