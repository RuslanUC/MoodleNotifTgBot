from tortoise import fields, Model

import models


class User(Model):
    id: int = fields.BigIntField(pk=True)
    name: str = fields.CharField(max_length=256)
    login: str = fields.CharField(max_length=256, unique=True)
    password: str = fields.TextField()

    tgusers: fields.ReverseRelation[models.TgUser]
