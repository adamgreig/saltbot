# Saltbot
# Copyright 2015 Adam Greig
# Released under the MIT license. See LICENSE file for details.

import sys
import logging
import logging.config

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
        self.check_config()
        self.configure_logging()
        return self.cfg

    def check_config(self):
        for sec in ['web', 'database', 'irc', 'logs', 'github', 'commands',
                    'repos']:
            if sec not in self.cfg:
                raise ValueError("Missing {} section in config".format(sec))
        self.check_web_config()
        self.check_db_config()
        self.check_irc_config()
        self.check_github_config()
        self.check_commands_config()
        self.check_repos_config()

    def check_web_config(self):
        web = self.cfg['web']
        if 'url' not in web:
            raise ValueError("Must specify web.url in config")
        if web['url'][-1] == "/":
            self.cfg['web']['url'] = web['url'][:-1]
        if 'per_page' not in web:
            self.cfg['web']['per_page'] = 20
        try:
            self.cfg['web']['per_page'] = int(web['per_page'])
        except ValueError:
            raise ValueError("web.per_page must be an integer")

        if not (
                ('socket' in web and 'mode' in web) or
                ('host' in web and 'port' in web)):
            raise ValueError("Missing socket/mode or host/port in config")

    def check_db_config(self):
        db = self.cfg['database']
        engine = db.get('engine', None)
        if engine == "sqlite":
            if 'file' not in db:
                raise ValueError("Missing database.file in config")
        elif engine == "postgresql":
            if 'database' not in db:
                raise ValueError("Missing database.database in config")
        else:
            raise ValueError("Unsupported database.engine in config")

    def check_irc_config(self):
        irc = self.cfg['irc']
        for setting in 'server', 'port', 'channel', 'nick':
            if setting not in irc:
                raise ValueError("Missing required irc.{} in config"
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

    def check_commands_config(self):
        cmds = self.cfg['commands']
        if 'ship' not in cmds:
            raise ValueError("Missing commands.ship")
        ship = cmds['ship']
        if 'it' not in ship:
            raise ValueError("Missing commands.ship.it")
        if 'target' not in ship:
            raise ValueError("Missing commands.ship.target")
        if 'expr_form' not in ship:
            self.cfg['commands']['ship']['expr_form'] = 'glob'

    def check_repos_config(self):
        repos = self.cfg['repos']
        for repo in repos:
            for branch in repos[repo]:
                if 'target' not in repos[repo][branch]:
                    raise ValueError("No target specified for repos.{}.{}"
                                     .format(repo, branch))

    def configure_logging(self):
        logging.config.dictConfig(self.cfg['logs'])
