# Saltbot
# Copyright 2015 Adam Greig
# Licensed under MIT license, see LICENCE file for details.


import string
import logging

try:
    from queue import Empty
except ImportError:
    from Queue import Empty

import irc.bot
import irc.strings

logger = logging.getLogger("saltbot.ircbot")


class IRCBot(irc.bot.SingleServerIRCBot):
    def __init__(self, config, ircmq, irccq):
        logger.info("Connecting to server")
        self.config = config
        self.ircmq = ircmq
        self.irccq = irccq
        self.server = config['irc']['server']
        self.port = config['irc']['port']
        self.channel = config['irc']['channel']
        self.nick = config['irc']['nick']
        self.auth_check_in_flight = None
        super(IRCBot, self).__init__([(self.server, self.port)],
                                     self.nick, self.nick)

    def on_nicknameinuse(self, c, e):
        logger.info("Nickname in use, trying alternative")
        c.nick(c.get_nickname() + "_")

    def on_welcome(self, c, e):
        logger.info("Welcome message received")
        if 'password' in self.config['irc']:
            logger.info("Identifying with NickServ")
            c.privmsg('NickServ',
                      "IDENTIFY {}".format(self.config['irc']['password']))

        logger.info("Joining channel {}".format(self.channel))
        c.join(self.channel)

    def on_join(self, c, e):
        logger.info("Joined channel {}".format(self.channel))
        c.execute_every(1, self.check_queue)

    def on_privmsg(self, c, e):
        logger.info("PRIVMSG received {} {}".format(e.source, e.arguments[0]))
        sender = e.source.split("!")[0]
        if sender in self.config['irc']['owners']:
            # Handle commands from owners
            self.check_ident_and_cmd(sender, e.arguments[0])

    def on_privnotice(self, c, e):
        # Strip non-printable characters from log output
        msg = ''.join(c for c in e.arguments[0] if c in string.printable)
        logger.info("NOTICE received {} {}".format(e.source, msg))
        sender = e.source.split("!")[0]
        if sender == "NickServ":
            # Handle NickServ replying to authentication request
            self.handle_nickserv(e)

    def check_ident_and_cmd(self, sender, msg):
        """
        Verify with NickServ that *sender* is identified, and if so,
        execute *msg*.
        """
        logger.info("Validating identity of {} with NickServ".format(sender))
        self.auth_check_in_flight = (sender, msg)
        self.connection.privmsg("NickServ", "ACC {}".format(sender))

    def handle_nickserv(self, e):
        """
        Respond to a NickServ privmsg.
        Currently deals with ACC responses for checking users are identified.
        """
        msg = e.arguments[0]
        parts = msg.split()

        if self.auth_check_in_flight and len(parts) == 3 and parts[1] == "ACC":
            who, what = self.auth_check_in_flight
            if parts[0] == who and parts[2] == "3":
                logger.info("Identity for {} valid, issuing command: {}"
                            .format(who, what))
                self.irccq.put(("cmd", (who, what)))
            else:
                logger.info("Could not validate identity for {}".format(who))
                self.connection.privmsg(who, "Please identify to NickServ")

    def check_queue(self):
        """
        Periodically check the ircmq for new things to do.

        Commands include:
            "pubmsg" : message
                send `message` to the current channel
            "privmsg" : (user, message)
                send `message` to `user`
        """
        while True:
            try:
                cmd, arg = self.ircmq.get_nowait()
            except Empty:
                break
            else:
                if cmd == "pubmsg":
                    logger.info("Sending [{}] {}".format(self.channel, arg))
                    self.connection.privmsg(self.channel, arg)
                elif cmd == "privmsg":
                    logger.info("Sending [{}] {}".format(arg[0], arg[1]))
                    self.connection.privmsg(arg[0], arg[1])


def run(config, ircmq, irccq):
    bot = IRCBot(config, ircmq, irccq)
    bot.start()
