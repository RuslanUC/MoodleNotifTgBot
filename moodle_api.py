import re
from datetime import datetime
from typing import Optional

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from config import BASE_URL
from models import Notification, User
from models.session import Session


class MoodleApi:
    USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"

    def __init__(self, user_id: int, session_id: str, session_key: str):
        self._user_id = user_id
        self._session_id = session_id
        self._session_key = session_key

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def session_key(self) -> str:
        return self._session_key

    async def getNotifications(self, limit: int = 10, offset: int = 0) -> list[Notification]:
        headers = {"User-Agent": self.USER_AGENT}
        params = {"sesskey": self._session_key, "info": "message_popup_get_popup_notifications"}
        payload = [{
            "index": 0,
            "methodname": "message_popup_get_popup_notifications",
            "args": {"limit": limit, "offset": offset, "useridto": str(self._user_id)}
        }]

        async with ClientSession(cookies={"MoodleSession": self._session_id}, headers=headers) as cl:
            resp = await cl.post(f"{BASE_URL}/lib/ajax/service.php", params=params, json=payload)
            j = await resp.json()
        if not j or j[0]["error"] or not j[0]["data"]["notifications"]:
            return []
        notifications = j[0]["data"]["notifications"]
        existing_ids = set(await Notification.filter(id__in=[notif["id"] for notif in notifications])
                           .values_list('id', flat=True))
        if len(existing_ids) == len(notifications):
            return []

        user = await User.get(id=self._user_id)

        result = []
        for notif in notifications:
            if notif["id"] in existing_ids:
                continue
            result.append(await Notification.create(
                id=notif["id"],
                url=notif["contexturl"],
                message=notif["smallmessage"],
                created_at=datetime.utcfromtimestamp(notif["timecreated"]),
                user=user,
            ))

        result.sort(key=lambda n: n.created_at)

        return result

    @classmethod
    async def login(cls, login: str, password: str):
        headers = {
            'content-type': 'application/x-www-form-urlencoded',
            'origin': BASE_URL,
            'referer': f'{BASE_URL}/login/index.php',
            'user-agent': cls.USER_AGENT,
        }

        data = {
            'logintoken': None,
            'username': login,
            'password': password,
        }

        async with ClientSession() as sess:
            token_req = await sess.get(f"{BASE_URL}/login/index.php")
            text = await token_req.text()
            tokens = re.findall(r'<input type="hidden" name="logintoken" value="([a-zA-Z0-9-_]{32})">', text)
            if not tokens:
                raise ValueError("Unable to find login token, maybe moodle sent invalid response")
            data["logintoken"] = tokens[0]

            resp = await sess.post(f"{BASE_URL}/login/index.php", headers=headers, data=data)
            cookies = dict(sess.cookie_jar.filter_cookies(BASE_URL))
            if "MoodleSession" not in cookies:
                raise ValueError("Session cookie is not set!")

            text = await resp.text()

        session_id = cookies["MoodleSession"].value
        session_key = text.split("sesskey\":\"")[1].split("\"")[0]
        user_id = int(text.split("data-user-id=\"")[1].split("\"")[0])
        return cls(user_id, session_id, session_key)

    async def get_name(self) -> Optional[str]:
        headers = {"User-Agent": self.USER_AGENT}

        async with ClientSession(cookies={"MoodleSession": self._session_id}, headers=headers) as cl:
            resp = await cl.get(f"{BASE_URL}/my/courses.php")
            text = await resp.text()

        soup = BeautifulSoup(text, 'html.parser')
        a = soup.select("div.logininfo > a:nth-child(1)")
        if not a:
            return
        return a[0].text.strip()

    @classmethod
    async def touch_session(cls, session: Session) -> bool:
        headers = {"User-Agent": cls.USER_AGENT}
        params = {"sesskey": session.session_key, "info": "core_session_touch"}
        payload = [{
            "index": 0,
            "methodname": "core_session_touch",
            "args": {}
        }]

        async with ClientSession(cookies={"MoodleSession": session.session_id}, headers=headers) as cl:
            resp = await cl.post(f"{BASE_URL}/lib/ajax/service.php", params=params, json=payload)
            j = await resp.json()

        return j and not j[0]["error"] and j[0]["data"]
