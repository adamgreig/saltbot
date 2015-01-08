# Saltbot
# Copyright 2015 Adam Greig
# Licensed under the MIT license, see LICENCE file for details.

import time
import logging
from queue import Empty

logger = logging.getLogger('saltbot.exchange')


class Exchange:
    def __init__(self, config, webq, ircq, sltq):
        self.cfg = config
        self.webq = webq
        self.ircq = ircq
        self.sltq = sltq

    def run(self):
        logger.info("Exchange started")
        while True:
            try:
                item = self.webq.get_nowait()
            except Empty:
                time.sleep(1)
                continue
            else:
                if item.get('__type') != "webhook_push":
                    continue
                if item['repo_name'] in self.cfg['repos']:
                    branch = item['gitref'].split("/", 2)[2]
                    repo_cfg = self.cfg['repos'][item['repo_name']]
                    if branch in repo_cfg:
                        logger.info("Push received to a configured branch")
                        target = repo_cfg[branch]['target']
                        expr_form = repo_cfg[branch].get('expr_form', 'glob')
                        logger.info("Target ({}): {}"
                                    .format(expr_form, target))
                        self.ircq.put("Push to {} {} by {}, highstating {} {}"
                                      .format(item['repo_name'], branch,
                                              item['pusher'], expr_form,
                                              target))
                        self.sltq.put((target, expr_form))
                    else:
                        logger.info("Push was not to a configured branch")
                else:
                    logger.info("Push was not to a configured repository")


def run(config, webq, ircq, sltq):
    exchange = Exchange(config, webq, ircq, sltq)
    exchange.run()
