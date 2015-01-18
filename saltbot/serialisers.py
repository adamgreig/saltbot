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
        r['job_url'] = "{}/jobs/{}".format(self.url, obj.jobs[0].jid)
        r['job_jid'] = obj.jobs[0].jid
        r['url'] = "{}/pushes/{}".format(self.url, obj.id)
        r['id'] = obj.id
        r['branch'] = obj.gitref.split("/")[2]
        return r

    def serialise_saltjob(self, obj):
        r = {k: str(getattr(obj, k)) for k in obj._meta.get_field_names()}
        del r['github_push']
        del r['id']
        if hasattr(obj, 'no_errors'):
            r['no_errors'] = bool(obj.no_errors)
        if hasattr(obj, 'all_in'):
            r['all_in'] = bool(obj.all_in)
        ghp = obj.github_push
        ghp_fields = ghp._meta.get_field_names()
        r['push'] = {k: str(getattr(ghp, k)) for k in ghp_fields}
        r['push']['branch'] = ghp.gitref.split("/")[2]
        r['push']['id'] = ghp.id
        r['push']['url'] = "{}/pushes/{}".format(self.url, ghp.id)
        r['url'] = "{}/jobs/{}".format(self.url, obj.jid)
        return r

    def serialise_saltjobminion(self, obj):
        jid = obj.job.jid
        r = {
            "minion": obj.minion,
            "url": "{}/jobs/{}/minions/{}".format(self.url, jid, obj.id),
            "id": obj.id,
            "jid": jid,
        }
        if hasattr(obj, 'no_errors'):
            if obj.no_errors is None:
                r['no_errors'] = True
            else:
                r['no_errors'] = bool(obj.no_errors)
        if hasattr(obj, 'num_results'):
            r['num_results'] = int(obj.num_results)
        if hasattr(obj, 'num_good') and obj.num_good is not None:
            r['num_good'] = int(obj.num_good)
        if hasattr(obj, 'num_results') and hasattr(obj, 'num_good'):
            if obj.num_results is not None and obj.num_good is not None:
                r['num_errors'] = int(obj.num_results) - int(obj.num_good)
        return r

    def serialise_saltminionresult(self, obj):
        r = {k: str(getattr(obj, k)) for k in obj._meta.get_field_names()}
        del r['id']

        r['minion'] = obj.minion.minion
        r['result'] = obj.result
        try:
            r['output'] = json.loads(obj.output)
        except ValueError:
            r['output'] = None
        return r
