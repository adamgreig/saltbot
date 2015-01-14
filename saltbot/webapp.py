# Saltbot
# Copyright 2015 Adam Greig
# Licensed under the MIT license, see LICENCE file for details.

import hmac
import logging

from flask import Flask, request, g, jsonify, abort
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.netutil import bind_unix_socket
from peewee import fn, JOIN_LEFT_OUTER, SQL

try:
    reloading
except NameError:
    reloading = False
else:
    import imp
    from . import database
    from . import serialisers
    imp.reload(database)
    imp.reload(serialisers)

from .database import Database
from .database import GitHubPush, SaltJob, SaltJobMinion, SaltMinionResult
from .serialisers import Serialise

app = Flask(__name__)
logger = logging.getLogger("saltbot.http")


def get_page(query):
    page = int(request.args.get('page', 1))
    per_page = app.config['web']['per_page']
    pages = query.count() // per_page + 1
    return page, pages, per_page


def bool_and(*args, **kwargs):
    """To do BOOL_AND() etc portably we swap depending on DB engine"""
    if app.config['database']['engine'] == "sqlite":
        return fn.Min(*args, **kwargs)
    elif app.config['database']['engine'] == "postgresql":
        return fn.Bool_And(*args, **kwargs)


@app.before_request
def before_request():
    g._db = Database(app.config)
    g._db.connect()
    g._serialise = Serialise(app.config)


@app.teardown_appcontext
def teardown_appcontext(error=None):
    if hasattr(g, '_db'):
        g._db.close()


@app.route("/")
def index():
    logger.info("index()")
    return "Hello World!"


@app.route("/pushes/")
def pushes():
    pushesq = GitHubPush.select().join(SaltJob)
    page, pages, pp = get_page(pushesq)
    pushes = [g._serialise(p) for p in pushesq.paginate(page, pp).iterator()]
    return jsonify(page=page, pages=pages, pushes=pushes)


@app.route("/pushes/<int:pushid>")
def push(pushid):
    try:
        push = GitHubPush.get(id=pushid)
    except GitHubPush.DoesNotExist:
        abort(404)
    return jsonify(**g._serialise(push))


@app.route("/jobs/")
def jobs():
    """
    Get all the SaltJobs we know about, and additionally:
        * Check for all_in by taking AND( COUNT(results) > 0 ).
          This is a little subtle as it's a nested aggregation so uses a
          subquery that selects everything we want plus the COUNT per-minion,
          then on the outer query performs the AND and groups by job.
        * Check for no_errors job-wide by taking AND(result) over all results.
          If some minions have no results, their AND(result) will be NULL,
          which bubbles up to a NULL at the top level that obscures whether
          any errors have actually been reported yet.
          So instead we can take the AND() again at the top level to clear
          this up.
    On top of that, in PostgreSQL (but not SQLite) all columns from the
    subquery must either appear inside an aggregate or the GROUP_BY,
    which means instead of just grouping by `id' and selecting * on the outer
    query, we must explicitly list the fields for the model. Sigh.
    """
    job_fields = SQL(
        '"id", "when", "jid", "expr_form", "target", "github_push_id"')
    no_errors_int = bool_and(SaltMinionResult.result).alias('no_errors_int')
    no_errors = bool_and(SQL('no_errors_int')).alias('no_errors')
    got_results = (fn.Count(SaltMinionResult.id) > 0).alias('got_results')
    all_in = bool_and(SQL('got_results')).alias('all_in')
    subq = (SaltJob
            .select(SaltJob, no_errors_int, got_results)
            .join(SaltJobMinion, JOIN_LEFT_OUTER)
            .join(SaltMinionResult, JOIN_LEFT_OUTER)
            .group_by(SaltJob, SaltJobMinion))
    jobsq = (SaltJob
             .select(job_fields, no_errors, all_in)
             .from_(subq.alias("subq"))
             .group_by(job_fields))
    page, pages, pp = get_page(jobsq)
    jobs = [g._serialise(j) for j in jobsq.paginate(page, pp).iterator()]
    return jsonify(page=page, pages=pages, jobs=jobs)


@app.route("/jobs/<jid>")
def job(jid):
    try:
        job = SaltJob.get(jid=jid)
    except SaltJob.DoesNotExist:
        abort(404)
    no_errors = bool_and(SaltMinionResult.result).alias('no_errors')
    num_results = fn.Count(SaltMinionResult.id).alias('num_results')
    minionsq = (SaltJobMinion
                .select(SaltJobMinion, no_errors, num_results)
                .join(SaltMinionResult, JOIN_LEFT_OUTER)
                .group_by(SaltJobMinion)
                .where(SaltJobMinion.job == job))
    minions = [g._serialise(m) for m in minionsq.iterator()]
    no_errors = all(m['no_errors'] for m in minions)
    all_in = all(m['num_results'] > 0 for m in minions)
    return jsonify(minions=minions, no_errors=no_errors, all_in=all_in,
                   **g._serialise(job))


@app.route("/jobs/<jid>/minions/<int:minion>")
def minionresults(jid, minion):
    try:
        job = SaltJob.get(jid=jid)
        minion = SaltJobMinion.get(id=minion, job=job)
    except (SaltJob.DoesNotExist, SaltJobMinion.DoesNotExist):
        abort(404)
    resultsq = (SaltMinionResult
                .select()
                .join(SaltJobMinion)
                .where(SaltMinionResult.minion == minion))
    results = [g._serialise(r) for r in resultsq.iterator()]

    no_errors = all(r['result'] for r in results)
    no_errors = bool(no_errors)

    return jsonify(minion=minion.minion, no_errors=no_errors, results=results)


@app.route("/webhook", methods=["POST"])
def webhook():
    logger.info("Webhook received")

    secret = app.config['github']['secret'].encode()
    their_sig = request.headers.get('X-Hub-Signature')
    my_sig = hmac.new(secret, request.data, 'SHA1').hexdigest()
    if not hmac.compare_digest(their_sig, "sha1={}".format(my_sig)):
        logger.warn("Invalid signature received!")
        return "Invalid signature", 403
    logger.info("HMAC signature valid")

    if request.headers.get('X-GitHub-Event') == 'push':
        event = request.get_json()
        push = {}
        push['gitref'] = event['ref']
        push['repo_name'] = event['repository']['full_name']
        push['repo_url'] = event['repository']['url']
        push['commit_id'] = event['head_commit']['id']
        push['commit_msg'] = event['head_commit']['message']
        push['commit_ts'] = event['head_commit']['timestamp']
        push['commit_url'] = event['head_commit']['url']
        push['commit_author'] = event['head_commit']['author']['username']
        push['pusher'] = event['pusher']['name']
        logger.info("Details: {}".format(push))
        app.config['webpq'].put(("github_push", push))

    if request.headers.get('X-GitHub-Event') == 'ping':
        logger.info("Received GitHub ping")

    return "OK"


def run(config, webpq):
    logger.info("App starting up")
    app.config.update(config)
    app.config['webpq'] = webpq
    server = HTTPServer(WSGIContainer(app))
    if config['web'].get('socket'):
        mode = int(str(config['web'].get('mode', 777)), 8)
        socket = bind_unix_socket(config['web'].get('socket'), mode=mode)
        server.add_socket(socket)
    else:
        port = config['web'].get('port', 8000)
        host = config['web'].get('host', 'localhost')
        server.listen(port, address=host)
    IOLoop.instance().start()
