# Saltbot
# Copyright 2015 Adam Greig
# Released under the MIT license. See LICENSE file for details.

import json

from .database import GitHubPush, SaltJob, SaltJobMinion, SaltMinionResult


class Serialise:
    def __init__(self, config):
        self.cfg = config
        self.url = self.cfg['web']['url']

    def __call__(self, obj):
        if isinstance(obj, GitHubPush):
            return self.serialise_githubpush(obj)
        elif isinstance(obj, SaltJob):
            return self.serialise_saltjob(obj)
        elif isinstance(obj, SaltJobMinion):
            return self.serialise_saltjobminion(obj)
        elif isinstance(obj, SaltMinionResult):
            return self.serialise_saltminionresult(obj)

    def serialise_githubpush(self, obj):
        r = {k: str(getattr(obj, k)) for k in obj._meta.get_field_names()}
        r['job_urls'] = ["{}/jobs/{}".format(self.url, j.jid)
                         for j in obj.jobs]
        r['url'] = "{}/pushes/{}".format(self.url, obj.id)
        return r

    def serialise_saltjob(self, obj):
        r = {k: str(getattr(obj, k)) for k in obj._meta.get_field_names()}
        del r['github_push']
        del r['id']
        if hasattr(obj, 'no_errors'):
            r['no_errors'] = bool(obj.no_errors)
        if hasattr(obj, 'all_in'):
            r['all_in'] = bool(obj.all_in)
        r['push_url'] = "{}/pushes/{}".format(self.url, obj.github_push.id)
        r['url'] = "{}/jobs/{}".format(self.url, obj.jid)
        return r

    def serialise_saltjobminion(self, obj):
        jid = obj.job.jid
        r = {
            "minion": obj.minion,
            "url": "{}/jobs/{}/minions/{}".format(self.url, jid, obj.id),
        }
        if hasattr(obj, 'no_errors'):
            if obj.no_errors is None:
                r['no_errors'] = True
            else:
                r['no_errors'] = bool(obj.no_errors)
        if hasattr(obj, 'num_results'):
            r['num_results'] = obj.num_results
        return r

    def serialise_saltminionresult(self, obj):
        r = {k: str(getattr(obj, k)) for k in obj._meta.get_field_names()}
        del r['id']
        del r['minion']
        del r['result']
        del r['output']

        r['minion'] = obj.minion.minion
        r['result'] = obj.result
        try:
            r['output'] = json.loads(obj.output)
        except ValueError:
            r['output'] = None
        return r
