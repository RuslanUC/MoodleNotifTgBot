from tortoise import fields, Model

import models


class Session(Model):
    id: int = fields.BigIntField(pk=True)
    user: models.User = fields.ForeignKeyField("models.User")
    session_id: str = fields.CharField(max_length=64)
    session_key: str = fields.CharField(max_length=128)
