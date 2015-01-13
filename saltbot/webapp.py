# Saltbot
# Copyright 2015 Adam Greig
# Licensed under the MIT license, see LICENCE file for details.

import hmac
import logging

from flask import Flask, request, g, jsonify
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.netutil import bind_unix_socket

try:
    reloading
except NameError:
    reloading = False
else:
    import imp
    from . import database
    imp.reload(database)

from .database import Database
from .database import GitHubPush, SaltJob, SaltJobMinion, SaltMinionResult

app = Flask(__name__)
logger = logging.getLogger("saltbot.http")
database = None


@app.before_request
def before_request():
    g._db = Database(app.config)
    g._db.connect()


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
    pushesq = GitHubPush.select()
    page = int(request.args.get('page', 1))
    pages = pushesq.count() // 20 + 1
    pushes = [p.to_dict() for p in pushesq.paginate(page, 20).iterator()]
    return jsonify(page=page, pages=pages, pushes=pushes)


@app.route("/pushes/<int:pushid>")
def push(pushid):
    push = GitHubPush.get(id=pushid)
    return jsonify(**push.to_dict())


@app.route("/jobs/")
def jobs():
    jobsq = SaltJob.select()
    page = int(request.args.get('page', 1))
    pages = jobsq.count() // 20 + 1
    jobs = [j.to_dict() for j in jobsq.paginate(page, 20).iterator()]
    return jsonify(page=page, pages=pages, jobs=jobs)


@app.route("/jobs/<int:jobid>")
def job(jobid):
    job = SaltJob.get(id=jobid)
    return jsonify(**job.to_dict())


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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    config = {"web": {"socket": "/tmp/saltbot-app.sock", "mode": 777}}
    import multiprocessing
    webpq = multiprocessing.Queue()
    run(config, webpq)
