# Saltbot
# Copyright 2015 Adam Greig
# Released under the MIT license. See LICENSE file for details.

__author__ = "Adam Greig"
__version__ = "0.0.1"
__version_info__ = tuple([int(d) for d in __version__.split(".")])
__license__ = "MIT License"

import sys
import time
import signal
import logging
import multiprocessing

try:
    from queue import Empty
    from imp import reload
except ImportError:
    from Queue import Empty

logger = logging.getLogger("saltbot")

from . import config
from . import webapp
from . import ircbot
from . import exchange
from . import saltshaker

modules = ("config", "webapp", "ircbot", "exchange", "saltshaker")


class SaltBot:
    def __init__(self):
        self.cfg = config.ConfigParser().load()
        self.commands = {
            "quit": self.command_quit,
            "say": self.command_say,
            "reload": self.command_reload,
            "highstate": self.command_highstate,
            "ship": self.command_ship,
            "help": self.command_help,
        }

    def run(self):
        logger.info("Saltbot starting up")

        # Ignore signals when creating Queues
        self.block_sigs()

        # IRC Message Queue, *->IRC
        self.ircmq = multiprocessing.Queue()
        # IRC Command Queue, IRC->core
        self.irccq = multiprocessing.Queue()
        # Web Push Queue, web->exchange
        self.webpq = multiprocessing.Queue()
        # Salt Command Queue, exchange->salt
        self.sltcq = multiprocessing.Queue()
        # Salt Result Queue, salt->exchange
        self.sltrq = multiprocessing.Queue()

        # Respond to signals again
        self.unblock_sigs()

        self.start_exc()
        self.start_irc()
        self.start_slt()
        self.start_web()

        self.loop()

    def block_sigs(self):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

    def unblock_sigs(self):
        signal.signal(signal.SIGINT, self.signal)
        signal.signal(signal.SIGTERM, self.signal)

    def start_exc(self):
        logger.info("Starting Exchange process")
        self.excp = multiprocessing.Process(
            target=exchange.run, name="Saltbot Exchange",
            args=(self.cfg, self.ircmq, self.webpq, self.sltcq, self.sltrq))
        self.excp.daemon = True
        self.block_sigs()
        self.excp.start()
        self.unblock_sigs()

    def start_irc(self):
        logger.info("Starting IRC process")
        self.ircp = multiprocessing.Process(
            target=ircbot.run, name="Saltbot IRC",
            args=(self.cfg, self.ircmq, self.irccq))
        self.ircp.daemon = True
        self.block_sigs()
        self.ircp.start()
        self.unblock_sigs()

    def start_slt(self):
        logger.info("Starting Salt process")
        self.sltp = multiprocessing.Process(
            target=saltshaker.run, name="Saltbot Salt",
            args=(self.cfg, self.sltcq, self.sltrq))
        self.sltp.daemon = True
        self.block_sigs()
        self.sltp.start()
        self.unblock_sigs()

    def start_web(self):
        logger.info("Starting web process")
        self.webp = multiprocessing.Process(
            target=webapp.run, name="Saltbot Web",
            args=(self.cfg, self.webpq))
        self.webp.daemon = True
        self.block_sigs()
        self.webp.start()
        self.unblock_sigs()

    def loop(self):
        """
        Check all child processes are still alive and restart if required.
        Handle incoming commands from IRC.
        """
        while True:
            # Restart dead child processes
            if not self.ircp.is_alive():
                logger.warn("IRC process died, restarting")
                self.start_irc()
            if not self.webp.is_alive():
                logger.warn("Web process died, restarting")
                self.start_web()
            if not self.sltp.is_alive():
                logger.warn("Salt process died, restarting")
                self.start_slt()
            if not self.excp.is_alive():
                logger.warn("Exchange process died, restarting")
                self.start_exc()

            # Handle commands from IRC
            try:
                cmd, args = self.irccq.get_nowait()
            except Empty:
                pass
            else:
                if cmd == "cmd":
                    self.process_irc_command(*args)

            time.sleep(1)

    def signal(self, num, frame):
        logger.warn("Terminating due to signal")
        self.terminate()

    def terminate(self):
        logger.warn("Shutting down child processes")
        children = "excp", "sltp", "ircp", "webp"
        for child in children:
            if hasattr(self, child) and getattr(self, child) is not None:
                try:
                    getattr(self, child).terminate()
                except AttributeError:
                    pass
        for child in children:
            if hasattr(self, child) and getattr(self, child) is not None:
                try:
                    getattr(self, child).join()
                except AttributeError:
                    pass
        logger.warn("Final exit")
        sys.exit()

    def process_irc_command(self, who, message):
        logger.info("Processing IRC command <{}> {}".format(who, message))
        if len(message.split()) > 1:
            cmd, arg = message.split(None, 1)
            arg = arg.strip()
        else:
            cmd = message.strip()
            arg = None

        if cmd in self.commands:
            logger.info("Executing command {}".format(cmd))
            self.commands[cmd](who, arg)
        else:
            logger.info("Unknown command {}".format(cmd))
            self.irc_send(who, "Unknown command")

    def irc_send(self, who, msg):
        self.ircmq.put(("privmsg", (who, msg)))

    def command_help(self, who, arg):
        self.irc_send(who, "Available commands:")
        self.irc_send(who, "  quit                 Closes saltbot")
        self.irc_send(who, "  help                 Display this message")
        self.irc_send(who, "  say <message>        Says <message> on IRC")
        self.irc_send(who, "  ship <'it'|target>   Ship it!")
        self.irc_send(who, "  highstate <target> [expr_form] [wait_gitfs]")
        self.irc_send(who, "  reload <module>    Reloads <module>, one of:")
        self.irc_send(who, "    {}".format(", ".join(modules)))

    def command_reload(self, who, arg):
        if not arg or arg not in modules:
            self.irc_send(who, "Must specify a module, one of:")
            self.irc_send(who, ', '.join(modules))
            return
        else:
            self.irc_send(who, "Reloading {}".format(arg))
            logger.info("Reloading {}".format(arg))
            reload(globals()[arg])
            if arg == "config":
                self.cfg = config.ConfigParser().load()
            elif arg == "webapp":
                self.webp.terminate()
                self.webp.join()
                self.start_web()
            elif arg == "ircbot":
                self.ircp.terminate()
                self.ircp.join()
                self.start_irc()
            elif arg == "saltshaker":
                self.sltp.terminate()
                self.sltp.join()
                self.start_slt()
            elif arg == "exchange":
                self.excp.terminate()
                self.excp.join()
                self.start_exc()

    def command_highstate(self, who, arg):
        if not arg or len(arg.split()) < 1:
            self.irc_send(
                who, "Usage: highstate <target> [expr_form] [wait_gitfs]")
            logger.info("Invalid IRC highstate received")
            return

        args = arg.split()
        event = {"who": who, "target": args[0]}

        if len(args) >= 2:
            event["expr_form"] = args[1]
        else:
            event["expr_form"] = "glob"

        if len(args) >= 3:
            event["wait_gitfs"] = bool(args[2])
        else:
            event["wait_gitfs"] = False

        logger.info("Sending IRC highstate request")
        self.irc_send(who, "Highstate request received, processing")
        self.webpq.put(("irc_highstate", event))

    def command_ship(self, who, arg):
        if not arg or len(arg.split()) != 1:
            self.irc_send(who, "Invalid ship command. Use: ship <it|target>")
            logger.info("Invalid IRC ship command received")
            return

        if arg == "it":
            target = self.cfg['commands']['ship']['it']
        else:
            target = self.cfg['commands']['ship']['target'].format(arg)

        event = {"who": who, "target": target, "wait_gitfs": False}
        event['expr_form'] = self.cfg['commands']['ship']['expr_form']
        logger.info("Sending highstate request via IRC ship")
        self.irc_send(
            who, "Ship request received, highstating {}".format(target))
        self.webpq.put(("irc_highstate", event))

    def command_quit(self, who, arg):
        self.irc_send(who, "Shutting down.")
        logger.warn("Quitting due to command")
        self.terminate()

    def command_say(self, who, arg):
        if arg:
            self.ircmq.put(("pubmsg", arg))
        else:
            self.irc_send(who, "Must specify a message")


def main():
    """
    Runs Saltbot
    Entry point: saltbot
    """
    saltbot = SaltBot()
    saltbot.run()


def createtables():
    """
    Creates DB tables
    Entry point: saltbot-createtables
    """
    import peewee
    from . import database
    saltbot = SaltBot()
    db = database.Database(saltbot.cfg)
    try:
        db.create_tables()
    except peewee.OperationalError as e:
        print("Received error, ignoring:", e)


def droptables():
    """
    Drops DB tables
    Entry point: saltbot-droptables
    """
    from . import database
    saltbot = SaltBot()
    db = database.Database(saltbot.cfg)
    confirm = input("Confirm DROP all tables? (y)> ")
    if confirm == "y":
        db.drop_tables()
