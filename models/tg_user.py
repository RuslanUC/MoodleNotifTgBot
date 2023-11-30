from tortoise import fields, Model


class TgUser(Model):
    id: int = fields.BigIntField(pk=True)
    moodle_users: fields.ManyToManyRelation = fields.ManyToManyField("models.User")
