# Saltbot
# Copyright 2015 Adam Greig
# Released under the MIT license. See LICENSE file for details.

import logging

from peewee import Proxy, SqliteDatabase, PostgresqlDatabase
from peewee import Model, CharField, TextField, DateTimeField, ForeignKeyField
from peewee import BooleanField

DBProxy = Proxy()
logger = logging.getLogger("saltbot.database")


class BaseModel(Model):
    def to_dict(self):
        return {k: str(getattr(self, k)) for k in self._meta.get_field_names()}

    class Meta:
        database = DBProxy


class GitHubPush(BaseModel):
    when = DateTimeField()
    gitref = CharField()
    repo_name = CharField()
    repo_url = CharField()
    commit_id = CharField()
    commit_msg = TextField()
    commit_ts = CharField()
    commit_url = CharField()
    commit_author = CharField()
    pusher = CharField()


class SaltJob(BaseModel):
    when = DateTimeField()
    jid = CharField()
    expr_form = CharField()
    target = TextField()
    github_push = ForeignKeyField(GitHubPush, related_name='jobs', null=True)


class SaltJobMinion(BaseModel):
    job = ForeignKeyField(SaltJob, related_name='minions')
    minion = CharField()


class SaltMinionResult(BaseModel):
    minion = ForeignKeyField(SaltJobMinion, related_name='results')
    key_state = CharField(null=True)
    key_id = CharField(null=True)
    key_name = CharField(null=True)
    key_func = CharField(null=True)
    comment = TextField(null=True)
    result = BooleanField(null=True)
    output = TextField()


tables = [GitHubPush, SaltJob, SaltJobMinion, SaltMinionResult]


class Database:
    def __init__(self, config):
        self.cfg = config
        dbcfg = self.cfg['database']
        if dbcfg['engine'] == "sqlite":
            filename = dbcfg['file']
            self.db = SqliteDatabase(filename)
        elif dbcfg['engine'] == "postgresql":
            args = dict(dbcfg)
            del args['engine']
            database = args['database']
            del args['database']
            self.db = PostgresqlDatabase(database, **args)
        else:
            raise ValueError("No supported database engine found in config")
        DBProxy.initialize(self.db)

    def create_tables(self):
        logger.info("Creating database tables")
        self.connect()
        self.db.create_tables(tables)
        self.close()

    def drop_tables(self):
        logger.warn("Dropping database tables")
        self.connect()
        self.db.drop_tables(tables)
        self.close()

    def connect(self):
        self.db.connect()

    def close(self):
        self.db.close()
