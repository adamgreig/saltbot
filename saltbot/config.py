# Saltbot
# Copyright 2015 Adam Greig
# Released under the MIT license. See LICENSE file for details.

import sys
import socket
import logging
import logging.handlers

import yaml

logger = logging.getLogger("saltbot.config")


_format_email = \
    """%(levelname)s from logger %(name)s (thread %(threadName)s)
    Time: %(asctime)s
    Location: %(pathname)s:%(lineno)d
    Module: %(module)s
    Function: %(funcName)s
    %(message)s"""

_format_string = \
    "[%(asctime)s.%(msecs)03.0fZ] %(levelname)s: %(name)s: %(message)s"
_date_format_string = '%Y-%m-%dT%H:%M:%S'


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
        self.check_logs_config()
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

    def check_logs_config(self):
        logs = self.cfg['logs']
        if 'levels' not in logs:
            raise ValueError("Missing required logs.levels config")
        if 'file' not in logs:
            self.cfg['logs']['file'] = None
        if 'syslog' not in logs:
            self.cfg['logs']['syslog'] = {}
        if 'email' in logs:
            self.check_logs_email_config(logs['email'])

    def check_logs_email_config(self, emails):
        for field in 'to', 'from', 'server':
            if field not in emails:
                raise ValueError("Missing required logs.email.{} config"
                                 .format(field))
        to_list = isinstance(emails['to'], list)
        to_str = isinstance(emails['to'], str)
        if not (to_list or to_str):
            raise ValueError("logs.email.to must be a list or string")
        if to_str:
            self.cfg['logs']['email']['to'] = [emails['to']]
        if not isinstance(emails['from'], str):
            raise ValueError("logs.email.from must be a string")
        if not isinstance(emails['server'], str):
            raise ValueError("logs.email.server must be a string")

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
        def str2level(level):
            return None if level == "NONE" else getattr(logging, level)

        root = logging.getLogger()
        root.setLevel(logging.DEBUG)
        root.handlers = []

        levels = self.cfg['logs']['levels']
        stderr_level = str2level(levels.get('stderr', "NONE"))
        file_level = str2level(levels.get('file', "NONE"))
        email_level = str2level(levels.get('email', "NONE"))
        syslog_level = str2level(levels.get('syslog', "NONE"))
        sentry_level = str2level(levels.get('sentry', "NONE"))

        if stderr_level is not None:
            self.configure_stderr_logging(root, stderr_level)

        if file_level is not None:
            self.configure_file_logging(root, file_level)

        if email_level is not None:
            self.configure_email_logging(root, email_level)

        if syslog_level is not None:
            self.configure_syslog_logging(root, syslog_level)

        if sentry_level is not None:
            self.configure_sentry_logging(root, sentry_level)

        logger.info("Logging initialised")

    def configure_stderr_logging(self, root, stderr_level):
        stderr_handler = logging.StreamHandler()
        stderr_handler.setFormatter(
            logging.Formatter(_format_string, _date_format_string))
        stderr_handler.setLevel(stderr_level)
        root.addHandler(stderr_handler)

    def configure_file_logging(self, root, file_level):
        file_name = self.cfg['logs']['file']
        file_handler = logging.handlers.WatchedFileHandler(file_name)
        file_handler.setFormatter(
            logging.Formatter(_format_string, _date_format_string))
        file_handler.setLevel(file_level)
        root.addHandler(file_handler)

    def configure_email_logging(self, root, email_level):
        email_to = self.cfg['logs']['email']['to']
        email_from = self.cfg['logs']['email']['from']
        email_server = self.cfg['logs']['email']['server']
        email_handler = logging.handlers.SMTPHandler(
            email_server, email_from, email_to, "Saltbot")
        email_handler.setLevel(email_level)
        email_handler.setFormatter(logging.Formatter(_format_email))
        root.addHandler(email_handler)

    def configure_syslog_logging(self, root, syslog_level):
        addr = self.cfg['logs']['syslog'].get('address', '/dev/log')
        facility = self.cfg['logs']['syslog'].get('facility', 'LOG_USER')
        socktype = self.cfg['logs']['syslog'].get('socktype', 'UDP')

        try:
            facility = getattr(logging.handlers.SysLogHandler, facility)
        except AttributeError:
            raise ValueError("Unknown syslog facility {}".format(facility))

        if socktype == "UDP":
            socktype = socket.SOCK_DGRAM
        elif socktype == "TCP":
            socktype = socket.SOCK_STREAM
        else:
            raise ValueError("Unknown syslog socktype {}".format(socktype))

        syslog_handler = logging.handlers.SysLogHandler(
            address=addr, facility=facility, socktype=socktype)
        syslog_handler.setLevel(syslog_level)
        fmtstring = "saltbot[%(process)d]: " + _format_string
        syslog_handler.setFormatter(
            logging.Formatter(fmtstring, _date_format_string))
        root.addHandler(syslog_handler)

    def configure_sentry_logging(self, root, sentry_level):
        if 'sentry' not in self.cfg['logs']:
            raise ValueError("Sentry logging specified but not configured")
        sentry_cfg = self.cfg['logs']['sentry']
        if 'release' not in sentry_cfg:
            try:
                import pkg_resources
                ver = pkg_resources.get_distribution("saltbot").version
                sentry_cfg['release'] = str(ver)
            except ImportError:
                pass
        try:
            from raven import Client as RavenClient
            from raven.handlers.logging import SentryHandler
        except ImportError:
            raise ValueError(
                "Sentry logging specified but Raven not installed")

        client = RavenClient(**sentry_cfg)
        sentry_handler = SentryHandler(client)
        sentry_handler.setLevel(sentry_level)
        root.addHandler(sentry_handler)
