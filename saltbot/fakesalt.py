# Saltbot
# Copyright 2015 Adam Greig
# Licensed under the MIT license, see LICENCE file for details.


import time
import random
import datetime


prefixes = ("endearing", "remarkable", "caring", "delightful", "glowing")
suffixes = ("puppy", "kitten", "biscuit", "muffin", "leaf", "flower")
states = ("file", "user", "service", "pkg", "git", "postgres_user")
funcs = ("present", "latest", "running", "absent", "username", "installed")


def random_names(n):
    names = set()
    while len(names) < n:
        name = random.choice(prefixes) + "." + random.choice(suffixes)
        if name not in names:
            names.add(name)
    return list(names)


def random_results(n):
    results = {}
    for _ in range(n):
        key_state = random.choice(states)
        key_id = random.choice(suffixes)
        key_name = random.choice(suffixes)
        key_func = random.choice(funcs)
        key = "_|-".join((key_state, key_id, key_name, key_func))
        r = {}
        r['comment'] = "Lorem ipsum dolor sit amet"
        r['name'] = key_name
        r['start'] = datetime.datetime.now().strftime("%H:%M:%S.%f")
        r['result'] = random.choice([True]*9 + [False])
        r['duration'] = random.randrange(10000) / 1000.0
        r['changes'] = random.choice([{}, {}, {}, {}, {'modified': 'things'}])
        r['warnings'] = ["this was generated using FakeSalt!"]
        r['__run_num__'] = random.randrange(200)
        results[key] = r
    return results


def make_jid():
    return datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")


class Event:
    def get_event_noblock(self):
        time.sleep(1)
        return {"tag": "salt/fileserver/gitfs/update"}


class client:
    class zmq:
        class ZMQError:
            pass

    class LocalClient:
        event = Event()
        opts = {"transport": None, "sock_dir": "/tmp/"}

        def run_job(self, tgt, fun, arg=(), expr_form='glob', ret='',
                    timeout=None, jid='', kwarg=None, **kwargs):
            n = random.randrange(1, 6)
            return {"jid": make_jid(), "minions": random_names(n)}

        def get_iter_returns(self, jid, minions, **kwargs):
            for minion in minions:
                n = random.randrange(5, 15)
                yield {minion: {'ret': random_results(n), 'out': 'highstate'}}


class utils:
    class event:
        def get_event(*args, **kwargs):
            return Event()
