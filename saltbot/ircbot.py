# Saltbot
# Copyright 2015 Adam Greig
# Licensed under MIT license, see LICENCE file for details.


import logging
from queue import Empty

import irc.bot
import irc.strings

logger = logging.getLogger("saltbot.ircbot")


class IRCBot(irc.bot.SingleServerIRCBot):
    def __init__(self, config, ircq):
        logger.info("Connecting to server")
        self.config = config
        self.ircq = ircq
        self.server = config['irc']['server']
        self.port = config['irc']['port']
        self.channel = config['irc']['channel']
        self.nick = config['irc']['nick']
        super().__init__([(self.server, self.port)], self.nick, self.nick)

    def on_nicknameinuse(self, c, e):
        logger.info("Nickname in use, trying alternative")
        c.nick(c.get_nickname() + "_")

    def on_welcome(self, c, e):
        logger.info("Welcome message received, joining channel")
        c.join(self.channel)

    def on_join(self, c, e):
        logger.info("Joined channel {}".format(self.channel))
        c.privmsg(self.channel, 'Saltbot ready')
        c.execute_every(1, self.check_queue)

    def check_queue(self):
        try:
            item = self.ircq.get_nowait()
        except Empty:
            return
        else:
            self.connection.privmsg(self.channel, item)


def run(config, ircq):
    bot = IRCBot(config, ircq)
    bot.start()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    config = {"irc": {"server": "chat.freenode.net",
                      "channel": "#adamgreig",
                      "nick": "saltbot",
                      "port": 6667}}
    import multiprocessing
    ircq = multiprocessing.Queue
    run(config, ircq)
