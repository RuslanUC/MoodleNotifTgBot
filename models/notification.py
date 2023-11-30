from datetime import datetime

from tortoise import fields, Model

import models


class Notification(Model):
    id: int = fields.BigIntField(pk=True)
    url: str = fields.TextField()
    message: str = fields.TextField()
    created_at: datetime = fields.DatetimeField()
    user: models.User = fields.ForeignKeyField("models.User")

    def __str__(self) -> str:
        return f"New notification ({self.created_at.strftime('%d.%m.%Y %H:%M:%S')}): \n\n{self.message}\n"
