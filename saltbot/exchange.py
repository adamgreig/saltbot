# Saltbot
# Copyright 2015 Adam Greig
# Licensed under the MIT license, see LICENCE file for details.

import time
import logging
import datetime
from queue import Empty

try:
    reloading
except NameError:
    reloading = False
else:
    import imp
    from . import database
    imp.reload(database)

from .database import Database, GitHubPush

logger = logging.getLogger('saltbot.exchange')


class Exchange:
    def __init__(self, config, ircmq, webpq, sltcq, sltrq):
        self.cfg = config
        self.ircmq = ircmq
        self.webpq = webpq
        self.sltcq = sltcq
        self.sltrq = sltrq
        self.db = Database(config)
        self.db.connect()

    def run(self):
        logger.info("Exchange started")
        while True:
            self.check_queue(self.webpq)
            self.check_queue(self.sltrq)
            time.sleep(1)

    def check_queue(self, q):
        try:
            event_type, event = q.get_nowait()
        except Empty:
            pass
        else:
            if event_type == "github_push":
                try:
                    self.handle_github_push(event)
                except (KeyError, ValueError):
                    logger.exception("Error processing GitHub Push")
            elif event_type == "salt_started":
                self.handle_salt_started(event)
            elif event_type == "salt_result":
                self.handle_salt_result(event)

    def handle_github_push(self, push):
        logger.info("Saving GitHub Push to database")
        ghpush = GitHubPush(when=datetime.datetime.now(), **push)
        ghpush.save()
        if push['repo_name'] in self.cfg['repos']:
            branch = push['gitref'].split("/", 2)[2]
            repo_cfg = self.cfg['repos'][push['repo_name']]
            if branch in repo_cfg:
                logger.info("Push received to a configured branch")
                target = repo_cfg[branch]['target']
                expr_form = repo_cfg[branch].get('expr_form', 'glob')
                logger.info("Target ({}): {}"
                            .format(expr_form, target))
                self.ircmq.put(
                    ("pubmsg", "Push to {} {} by {}, highstating {} {}"
                               .format(push['repo_name'], branch,
                                       push['pusher'], expr_form,
                                       target)))
                self.sltcq.put(("highstate", (target, expr_form, ghpush.id)))
            else:
                logger.info("Push was not to a configured branch")
        else:
            logger.info("Push was not to a configured repository")

    def handle_salt_started(self, message):
        self.ircmq.put(("pubmsg", message))

    def handle_salt_result(self, message):
        self.ircmq.put(("pubmsg", message))
        logger.info("Received salt result")


def run(config, ircmq, webpq, sltcq, sltrq):
    exchange = Exchange(config, ircmq, webpq, sltcq, sltrq)
    exchange.run()
