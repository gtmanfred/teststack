import flask_sqlalchemy


class BaseModel(flask_sqlalchemy.Model):
    def to_dict(self):
        return {column.key: getattr(self, attr) for attr, column in self.__mapper__.c.items()}


db = flask_sqlalchemy.SQLAlchemy(
    model_class=BaseModel,
    session_options={'expire_on_commit': True},
)
