# Saltbot
# Copyright 2015 Adam Greig
# Licensed under the MIT license, see LICENCE file for details.

import hmac
import logging

from flask import Flask, request
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.netutil import bind_unix_socket

app = Flask(__name__)
logger = logging.getLogger("saltbot.http")


@app.before_first_request
def startup():
    pass


@app.route("/")
def index():
    logger.info("index()")
    return "Hello World!"


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
        push = {"__type": "webhook_push"}
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
        app.config['webq'].put(push)

    if request.headers.get('X-GitHub-Event') == 'ping':
        logger.info("Received GitHub ping")

    return "OK"


def run(config, webq):
    logger.info("App starting up")
    app.config.update(config)
    app.config['webq'] = webq
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
    webq = multiprocessing.Queue()
    run(config, webq)
