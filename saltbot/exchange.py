# Saltbot
# Copyright 2015 Adam Greig
# Licensed under the MIT license, see LICENCE file for details.

import time
import logging
import datetime

try:
    from queue import Empty
    from imp import reload
except ImportError:
    from Queue import Empty

try:
    reloading
except NameError:
    reloading = False
else:
    from . import database
    reload(database)

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
            elif event_type == "irc_highstate":
                self.handle_irc_highstate(event)
            elif event_type == "salt_started":
                self.handle_salt_started(event)
            elif event_type == "salt_result":
                self.handle_salt_result(event)
            elif event_type == "salt_error":
                self.handle_salt_error(event)

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
                wait_gitfs = repo_cfg[branch].get('wait_gitfs', False)
                logger.info("Target (expr_form={}, wait_gitfs={}): {}"
                            .format(expr_form, wait_gitfs, target))
                commitmsg = push['commit_msg'][:77]
                if len(push['commit_msg']) > 77:
                    commitmsg += "..."
                self.ircmq.put(
                    ("pubmsg", "Push to {} {} by {}: {}"
                               .format(push['repo_name'], branch,
                                       push['pusher'], commitmsg)))
                self.ircmq.put(
                    ("pubmsg", "Going to highstate {} {}{}".format(
                        expr_form, target,
                        " (waiting for gitfs)" if wait_gitfs else "")))
                self.sltcq.put(("highstate", (target, expr_form,
                                              wait_gitfs, ghpush.id)))
            else:
                logger.info("Push was not to a configured branch")
        else:
            logger.info("Push was not to a configured repository")

    def handle_irc_highstate(self, args):
        logger.info("Handling IRC highstate request {}".format(args))
        ghpush = GitHubPush(when=datetime.datetime.now(),
                            pusher=args['who'], commit_msg="IRC Request",
                            gitref="//{}".format(args['expr_form']),
                            repo_name=args['target'], repo_url="#",
                            commit_author=args['who'], commit_url="#",
                            commit_ts=datetime.datetime.now(), commit_id="")
        ghpush.save()
        self.sltcq.put(("highstate", (args['target'], args['expr_form'],
                                      args['wait_gitfs'], ghpush.id)))

    def handle_salt_started(self, args):
        jid, minions = args
        self.ircmq.put(
            ("pubmsg", "Salt {} started to highstate {}"
                       .format(jid, ', '.join(minions))))
        self.ircmq.put(
            ("pubmsg", "{}/jobs/{}".format(self.cfg['web']['url'], jid)))

    def handle_salt_error(self, args):
        self.ircmq.put("pubmsg", "Error processing Salt job: {}".format(args))

    def handle_salt_result(self, args):
        jid, all_ok, m, n = args
        if all_ok and m == n:
            self.ircmq.put(
                ("pubmsg", "Salt JID {} finished, all OK".format(jid)))
        elif not all_ok:
            self.ircmq.put(
                ("pubmsg", "Salt JID {} finished, some errors".format(jid)))
        elif m != n:
            self.ircmq.put(
                ("pubmsg", "Salt JID {} finished, only {}/{} results"
                           .format(jid, m, n)))


def run(config, ircmq, webpq, sltcq, sltrq):
    exchange = Exchange(config, ircmq, webpq, sltcq, sltrq)
    try:
        exchange.run()
    except Exception:
        logger.exception("Unhandled exception")
        raise
