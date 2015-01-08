# Saltbot
# Copyright 2015 Adam Greig
# Licensed under the MIT license, see LICENCE file for details.

import time
import logging
from queue import Empty

logger = logging.getLogger('saltbot.saltshaker')


def run(config, sltq):
    while True:
        try:
            item = sltq.get_nowait()
        except Empty:
            time.sleep(1)
            continue
        else:
            logger.info("Received a command: {}".format(item))
