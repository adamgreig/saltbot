# Saltbot
# Copyright 2015 Adam Greig
# Licensed under the MIT license, see LICENCE file for details.

import time
import json
import logging
import datetime
from queue import Empty

logger = logging.getLogger('saltbot.saltshaker')

try:
    reloading
except NameError:
    reloading = False
else:
    import imp
    from . import fakesalt, database
    imp.reload(fakesalt)
    imp.reload(database)


try:
    import salt.client
    salt_client = salt.client.LocalClient()
except ImportError:
    logger.warn("Could not import 'salt', will use fake salt.")
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

    def highstate(self, target, expr, gh_push_id):
        job = salt_client.run_job(target, 'state.highstate', expr_form=expr)
        jid, minions = job['jid'], job['minions']
        iter_returns = salt_client.get_iter_returns(
            jid, minions, tgt=target, tgt_type=expr)
        now = datetime.datetime.now()
        dbjob = SaltJob(target=target, expr_form=expr, jid=jid,
                        when=now, github_push=gh_push_id)
        dbjob.save()
        dbminions = []
        for minion in minions:
            dbminion = SaltJobMinion(job=dbjob, minion=minion)
            dbminion.save()
            dbminions.append(dbminion)

        logger.info("Started Salt {} to highstate {}, DB ID {}"
                    .format(jid, minions, dbjob.id))
        self.sltrq.put(
            ("salt_started", "Salt JID {} running to highstate {}"
                             .format(jid, ', '.join(minions))))
        self.sltrq.put(
            ("salt_started", "{}jobs/{}"
                             .format(self.cfg['web']['url'], dbjob.id)))

        all_ok = True
        minions_heard_from = 0
        for ret in iter_returns:
            if not ret:
                continue
            for minion, result in ret.items():
                dbminion = dbminions[minions.index(minion)]
                if 'ret' not in result:
                    continue
                minions_heard_from += 1
                logger.info("Processing Salt results for {}".format(minion))
                for key, val in result['ret'].items():
                    out_j = json.dumps(val)
                    dbresult = SaltMinionResult(minion=dbminion, output=out_j)
                    try:
                        k_state, k_id, k_name, k_func = key.split("_|-")
                        dbresult.key_state = k_state
                        dbresult.key_id = k_id
                        dbresult.key_name = k_name
                        dbresult.key_func = k_func
                    except ValueError:
                        pass
                    try:
                        dbresult.result = bool(val['result'])
                        dbresult.comment = str(val['comment'])
                    except KeyError:
                        pass
                    else:
                        if not dbresult.result:
                            all_ok = False
                    dbresult.save()
        if all_ok and minions_heard_from == len(minions):
            logger.info("Salt results for {} in, all OK".format(jid))
            self.sltrq.put(("salt_result", "Salt JID {} finished, all OK"
                                           .format(jid)))
        else:
            logger.info("Salt results for {} in, not OK".format(jid))
            self.sltrq.put(("salt_result", "Salt JID {} finished with errors"
                                           .format(jid)))
        self.sltrq.put(
            ("salt_started", "{}jobs/{}"
                             .format(self.cfg['web']['url'], dbjob.id)))


def run(config, sltcq, sltrq):
    saltshaker = SaltShaker(config, sltcq, sltrq)
    saltshaker.run()
