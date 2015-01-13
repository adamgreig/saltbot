# Saltbot
# Copyright 2015 Adam Greig
# Released under the MIT license. See LICENSE file for details.

import sys
import logging

import yaml

logger = logging.getLogger("saltbot.config")


class ConfigParser:
    def load(self):
        if len(sys.argv) == 1:
            cfile = "saltbot.yml"
        elif len(sys.argv) == 2:
            cfile = sys.argv[1]
        else:
            raise ValueError("Usage: {} [config.yml]".format(sys.argv[0]))
        self.cfg = yaml.safe_load(open(cfile).read())

        return self.cfg

    def check_config(self):
        for sec in 'web', 'database', 'irc', 'logs', 'github', 'repos':
            if sec not in self.cfg:
                raise ValueError("Missing {} section from config".format(sec))
        self.check_web_config()
        self.check_db_config()
        self.check_irc_config()
        self.check_github_config()
        self.check_logs_config()
        self.check_repos_config()

    def check_web_config(self): 
        web = self.cfg['web']
        if 'url' not in web:
            raise ValueError("Must specify web.url in config")
        if not (
                ('socket' in web and 'mode' in web) or
                ('host' in web and 'port' in web)):
            raise ValueError("Missing socket/mode or host/port from config")

    def check_db_config(self): 
        db = self.cfg['database']
        if db.get('engine', None) == "sqlite":
            if 'file' not in db:
                raise ValueError("Missing database.file from config")
            else:
                raise ValueError("Unsupported database.engine in config")

    def check_irc_config(self):
        irc = self.cfg['irc']
        for setting in 'server', 'port', 'channel', 'nick':
            if setting not in irc:
                raise ValueError("Missing required irc.{} from config"
                                 .format(setting))
            if 'owners' not in irc:
                self.cfg['irc']['owners'] = []
                logger.warn("No IRC owners specified, commands cannot be run")
            if 'password' not in irc:
                self.cfg['irc']['password'] = None
                logger.warn("No IRC password specified, will not identify")

    def check_github_config(self):
        if 'secret' not in self.cfg['github']:
            raise ValueError("Missing required github.secret setting")

    def check_logs_config(self):
        logs = self.cfg['logs']
        if 'levels' not in logs:
            raise ValueError("Missing required logs.levels config")
        if 'file' not in logs:
            self.cfg['logs']['file'] = None
        if 'email' in logs:
            for field in 'to', 'from', 'server':
                if field not in logs['email']:
                    raise ValueError("Missing required logs.email.{} config"
                                     .format(field))
            to_list = isinstance(list, logs['email']['to'])
            to_str = isinstance(str, logs['email']['to'])
            if not (to_list or to_str):
                raise ValueError("logs.email.to must be a list or string")
            if to_str:
                self.cfg['logs']['email']['to'] = [logs['email']['to']]

    def configure_logging(self):
        def str2level(level):
            return None if level == "NONE" else getattr(logging, level)
        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        levels = self.cfg['logs']['levels']
        stderr_level = str2level(levels.get('stderr', "NONE"))
        file_level = str2level(levels.get('file', "NONE"))
        email_level = str2level(levels.get('email', "NONE"))

