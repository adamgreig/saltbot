# Saltbot
# Copyright 2015 Adam Greig
# Released under the MIT license. See LICENSE file for details.

import json

from .database import GitHubPush, SaltJob, SaltJobMinion, SaltMinionResult


def serialise(obj):
    if isinstance(obj, GitHubPush):
        return serialise_githubpush(obj)
    elif isinstance(obj, SaltJob):
        return serialise_saltjob(obj)
    elif isinstance(obj, SaltJobMinion):
        return serialise_saltjobminion(obj)
    elif isinstance(obj, SaltMinionResult):
        return serialise_saltminionresult(obj)
    else:
        raise TypeError("Can't serialise type {}".format(type(obj)))


def serialise_fields(obj, skip=None):
    """
    Turn any string, integer or bool fields into native Python types,
    returning a dict. Avoid any fields in 'skip'.
    """
    r = {}
    for k in obj._meta.get_field_names():
        if skip and k in skip:
            continue
        if isinstance(getattr(obj, k), type(None)):
            r[k] = None
            continue
        for t in (str, int, bool):
            if isinstance(getattr(obj, k), t):
                r[k] = t(getattr(obj, k))
                continue
    return r


def serialise_if_exists(obj, r, attr, t, default):
    """
    If hasattr(obj, attr) then if obj.attr is not None, r[attr]=t(obj.attr),
    or if it is None, r[attr]=default. Won't be added to r if not in obj.
    """
    if hasattr(obj, attr):
        if getattr(obj, attr) is not None:
            r[attr] = t(getattr(obj, attr))
        else:
            r[attr] = default


def serialise_githubpush(obj):
    r = serialise_fields(obj)
    r['branch'] = obj.gitref.split("/")[2]
    r['job_jid'] = obj.jobs[0].jid
    r['id'] = obj.id
    return r


def serialise_saltjob(obj):
    r = serialise_fields(obj, skip=['github_push', 'id'])
    r['push'] = serialise_githubpush(obj.github_push)
    serialise_if_exists(obj, r, 'all_in', bool, False)
    serialise_if_exists(obj, r, 'no_errors', bool, True)
    return r


def serialise_saltjobminion(obj):
    r = serialise_fields(obj, skip=['job', 'no_errors'])
    r['jid'] = obj.job.jid
    serialise_if_exists(obj, r, 'no_errors', bool, True)
    serialise_if_exists(obj, r, 'num_results', int, 0)
    serialise_if_exists(obj, r, 'num_good', int, 0)

    if hasattr(obj, 'num_good'):
        if obj.num_results is not None and obj.num_good is not None:
            r['num_errors'] = int(obj.num_results) - int(obj.num_good)
        else:
            r['num_errors'] = 0

    return r


def serialise_saltminionresult(obj):
    r = serialise_fields(obj, skip=['id', 'minion', 'output'])

    try:
        r['output'] = json.loads(obj.output)
    except ValueError:
        r['output'] = str(obj.output)

    return r
