# Saltbot
# Copyright 2015 Adam Greig
# Licensed under the MIT license, see LICENCE file for details.

import time
import json
import logging
import datetime

try:
    from queue import Empty
    from imp import reload
except ImportError:
    from Queue import Empty

logger = logging.getLogger('saltbot.saltshaker')

try:
    reloading
except NameError:
    reloading = False
else:
    from . import fakesalt, database
    reload(fakesalt)
    reload(database)


try:
    import salt.client
    salt_client = salt.client.LocalClient()
except ImportError:
    import warnings
    warnings.warn("Could not import 'salt', will use fake salt.")
    from . import fakesalt
    salt_client = fakesalt.FakeSalt()

from .database import Database, SaltJob, SaltJobMinion, SaltMinionResult


class SaltShaker:
    def __init__(self, config, sltcq, sltrq):
        self.cfg = config
        self.sltcq = sltcq
        self.sltrq = sltrq
        self.db = Database(config)
        self.db.connect()

    def run(self):
        while True:
            try:
                cmd, arg = self.sltcq.get_nowait()
            except Empty:
                time.sleep(1)
                continue
            else:
                logger.info("Received command {} {}".format(cmd, arg))
                if cmd == "highstate":
                    self.highstate(*arg)

    def start_salt(self, tgt, expr):
        job = salt_client.run_job(tgt, 'state.highstate', expr_form=expr)
        jid, minions = job['jid'], job['minions']
        iter_returns = salt_client.get_iter_returns(
            jid, minions, tgt=tgt, tgt_type=expr)
        return jid, minions, iter_returns

    def create_records(self, tgt, expr, jid, minions, push_id):
        now = datetime.datetime.now()
        dbjob = SaltJob(target=tgt, expr_form=expr, jid=jid,
                        when=now, github_push=push_id)
        dbjob.save()
        dbminions = []
        for minion in minions:
            dbminion = SaltJobMinion(job=dbjob, minion=minion)
            dbminion.save()
            dbminions.append(dbminion)
        return dbjob, dbminions

    def store_state_result(self, dbminion, key, val):
        out_j = json.dumps(val)
        dbresult = SaltMinionResult(minion=dbminion, output=out_j)

        # Get key based data
        try:
            k_state, k_id, k_name, k_func = key.split("_|-")
            dbresult.key_state = k_state
            dbresult.key_id = k_id
            dbresult.key_name = k_name
            dbresult.key_func = k_func
        except ValueError:
            pass

        # Get some other data fields that we care to store
        try:
            dbresult.result = bool(val['result'])
            dbresult.comment = str(val['comment'])
            dbresult.run_num = int(val['__run_num__'])
            dbresult.changed = val['changes'] != {}
        except KeyError:
            dbresult.result = False
        dbresult.save()

    def highstate(self, target, expr, gh_push_id):
        jid, minions, iter_returns = self.start_salt(target, expr)
        dbjob, dbminions = self.create_records(
            target, expr, jid, minions, gh_push_id)

        logger.info("Started Salt {} to highstate {}, DB ID {}"
                    .format(jid, minions, dbjob.id))
        self.sltrq.put(("salt_started", (jid, minions)))

        all_ok = True
        minions_heard_from = 0
        for ret in iter_returns:
            if not ret:
                continue
            for minion, result in ret.items():
                dbminion = dbminions[minions.index(minion)]
                if 'ret' not in result:
                    continue
                logger.info("Processing Salt results for {}".format(minion))
                minions_heard_from += 1
                for key, val in result['ret'].items():
                    self.store_state_result(dbminion, key, val)
                    if 'result' in val and not val['result']:
                        all_ok = False

        m, n = minions_heard_from, len(minions)
        logger.info("Results for {}: {}/{} results, all_ok={}"
                    .format(jid, m, n, all_ok))
        self.sltrq.put(("salt_result", (jid, all_ok, m, n)))


def run(config, sltcq, sltrq):
    saltshaker = SaltShaker(config, sltcq, sltrq)
    saltshaker.run()
