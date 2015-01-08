# Saltbot
# Copyright 2015 Adam Greig
# Released under the MIT license. See LICENSE file for details.

__author__ = "Adam Greig"
__version__ = "0.0.1"
__version_info__ = tuple([int(d) for d in __version__.split(".")])
__license__ = "MIT License"

import sys
import imp
import logging
import multiprocessing

import yaml

from . import webapp
from . import ircbot
from . import exchange
from . import saltshaker

modules = ("webapp", "ircbot", "exchange", "saltshaker")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("saltbot")


class SaltBot:
    def __init__(self):
        self.cfg = self.load_config()
        self.console_commands = {
            "quit": self.console_quit,
            "say": self.console_say,
            "reload": self.console_reload,
            "help": self.console_help,
        }

    def load_config(self):
        logger.info("Loading config")
        if len(sys.argv) == 1:
            cfile = "saltbot.yml"
        else:
            cfile = sys.argv[1]
        return yaml.load(open(cfile).read())

    def run(self):
        logger.info("Saltbot starting up")

        self.ircq = multiprocessing.Queue()
        self.ircp = multiprocessing.Process(
            target=ircbot.run, args=(self.cfg, self.ircq))

        self.webq = multiprocessing.Queue()
        self.webp = multiprocessing.Process(
            target=webapp.run, args=(self.cfg, self.webq))

        self.sltq = multiprocessing.Queue()
        self.sltp = multiprocessing.Process(
            target=saltshaker.run, args=(self.cfg, self.sltq))

        self.excp = multiprocessing.Process(
            target=exchange.run,
            args=(self.cfg, self.webq, self.ircq, self.sltq))

        self.processes = self.ircp, self.webp, self.sltp, self.excp

        self.excp.start()
        self.ircp.start()
        self.sltp.start()
        self.webp.start()

        self.console()

    def console(self):
        self.console_help(None)
        while True:
            cmd = input("> ")
            arg = None
            if " " in cmd:
                cmd, arg = cmd.split(" ")
                arg = arg.strip()

            if cmd in self.console_commands:
                self.console_commands[cmd](arg)
            else:
                print("Unknown command")

            if cmd == "quit":
                return

    def console_help(self, arg):
        print("saltbot command console")
        print("commands:")
        print("  quit               Closes saltbot")
        print("  help               Display this message")
        print("  say <message>      Says <message> on IRC")
        print("  reload <module>    Reloads <module>, one of:")
        print("    ", ", ".join(modules))

    def console_reload(self, arg):
        if not arg or arg not in modules:
            print("Must specify a module, one of:")
            print(modules)
            return
        else:
            print("Reloading {}".format(arg))
            imp.reload(globals()[arg])
            if arg == "webapp":
                self.webp.terminate()
                self.webp.join()
                self.webp = multiprocessing.Process(
                    target=webapp.run, args=(self.cfg, self.webq))
                self.webp.start()
            elif arg == "ircbot":
                self.ircp.terminate()
                self.ircp.join()
                self.ircp = multiprocessing.Process(
                    target=ircbot.run, args=(self.cfg, self.ircq))
                self.ircp.start()
            elif arg == "saltshaker":
                self.sltp.terminate()
                self.sltp.join()
                self.sltp = multiprocessing.Process(
                    target=saltshaker.run, args=(self.cfg, self.sltq))
                self.sltp.start()
            elif arg == "exchange":
                self.excp.terminate()
                self.excp.join()
                self.excp = multiprocessing.Process(
                    target=exchange.run,
                    args=(self.cfg, self.webq, self.ircq, self.sltq))
                self.excp.start()

    def console_quit(self, arg):
        print("Shutting down.")
        [p.terminate() for p in self.processes]
        [p.join() for p in self.processes]

    def console_say(self, arg):
        if not arg:
            print("Must specify a message")
        else:
            print("Saying {}".format(arg))
            self.ircq.put(arg)


def main():
    saltbot = SaltBot()
    saltbot.run()
