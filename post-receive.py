#!/usr/bin/env python
# Saltbot
# Copyright 2015 Adam Greig
# Released under the MIT license. See LICENSE file for details.
from __future__ import print_function

"""
Sample post-receive hook which sends notifications to Saltbot.

$ git config hooks.webhookurl http://saltbot.sample.com/api/webhook
$ git config hooks.webhooksecret hunter2
$ cp saltbot/post-receive.py .git/hooks/post-receive
$ chmod +x .git/hooks/post_receive
"""

import os
import sys
import json
import hmac
import getpass
import hashlib
import subprocess

from datetime import datetime

try:
    from urllib.error import URLError
    from urllib.parse import urlencode
    from urllib.request import urlopen, Request
except ImportError:
    from urllib import urlencode
    from urllib2 import urlopen, Request, URLError

def git(*args):
    args = ['git'] + list(args)
    git = subprocess.Popen(args, stdout=subprocess.PIPE)
    return git.stdout.read().strip()

def cfg(k):
    return git('config', str(k))

def repo_path():
    return os.path.abspath(os.getcwd())

def get_commit(new):
    commit = {}
    lines = git('--no-pager', 'show', '-s', '--quiet', new).split("\n")
    commit['id'] = lines[0].strip().split()[1].strip()
    author_email = lines[1].strip().split(": ", 1)[1].strip()
    commit['author'] = author_email.split('<', 1)[0].strip()
    timestamp = lines[2].strip().split(": ", 1)[1].strip()
    commit['message'] = "\n".join(l.strip() for l in lines[4:])

    basetime = datetime.strptime(timestamp[:-6], "%a %b %d %H:%M:%S %Y")
    tzstr = timestamp[-5:]
    commit['timestamp'] = basetime.strftime("%Y-%m-%dT%H:%M:%S") + tzstr
    
    return commit

def make_data(old, new, ref):
    commit = get_commit(new)
    data = {
        "ref": ref,
        "repository": {
            "full_name": repo_path(),
            "url": "#"
        },
        "head_commit": {
            "id": commit['id'],
            "message": commit['message'],
            "timestamp": commit['timestamp'],
            "url": "#",
            "author": {
                "username": commit['author']
            }
        },
        "pusher": {
            "name": getpass.getuser()
        }
    }
    return json.dumps(data)

def post(url, data, secret):
    enc_data = data.encode()
    sig = hmac.new(secret, enc_data, hashlib.sha1).hexdigest()
    headers = {
        "X-GitHub-Event": "push",
        "X-Hub-Signature": "sha1={}".format(sig),
        "Content-Type": "application/json"
    }
    req = Request(url, data=enc_data, headers=headers)
    try:
        urlopen(req)
    except URLError as e:
        print("Error posting to webhook: {}".format(e))

if __name__ == "__main__":
    for line in sys.stdin.readlines():
        old, new, ref = line.strip().split()
        data = make_data(old, new, ref)
        url = cfg('hooks.webhookurl').strip()
        secret = cfg('hooks.webhooksecret').strip()
        if url and secret:
            print("Submitting notification to {}".format(url))
            post(url, data, secret)
        else:
            print("Error: No webhook URL or secret configured")
