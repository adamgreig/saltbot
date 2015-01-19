# Saltbot
An IRC bot for [Salt](http://www.saltstack.com/community/) deployments.

## Features

 * Sits in your IRC channel all day
 * Finds out about pushes via GitHub webhooks or its own `post-receive.py`
 * When a push comes in, or a command from an authorised user on IRC,
 * Optionally waits for the next gitfs update() (for when salt-states is gitfs)
 * Runs salt.highstate via the Salt Python library (must be on salt master)
 * Targetting specific minions depending on the repo and branch pushed to
 * Fetches results as they come in
 * Returns status to IRC
 * Live updating web application to view current status and historic jobs
 * View full state output for every minion, highlighted by status

## Install

Currently runs on Python 2.7, 3.3 and 3.4.

    $ git clone https://github.com/adamgreig/saltbot.git
    $ cd saltbot
    saltbot$ virtualenv venv
    saltbot$ source venv/bin/activate
    saltbot$ pip install -r requirements.txt
    saltbot$ python setup.py develop
    saltbot$ cp saltbot.yml.sample saltbot.yml
    saltbot$ vi saltbot.yml

To use the `wait_gitfs` feature, in your Salt master configuration set:

    fileserver_events: True

## Usage

    saltbot$ saltbot
    [2015-01-08 06:46:33,346] INFO saltbot: Loading config
    [2015-01-08 06:46:33,350] INFO saltbot: Saltbot starting up
    [2015-01-08 06:46:33,356] INFO saltbot.exchange: Exchange started
    [2015-01-08 06:46:33,358] INFO saltbot.http: App starting up
    [2015-01-08 06:46:33,358] INFO saltbot.ircbot: Connecting to server
    [2015-01-08 06:46:39,655] INFO saltbot.ircbot: Welcome message received, joining channel
    [2015-01-08 06:46:46,385] INFO saltbot.ircbot: Joined channel #saltbot

Meanwhile, on IRC (via privmsg):

    07:07:07 adamgreig> help
    07:07:09 saltbot> Available commands:
    07:07:09 saltbot>   quit               Closes saltbot
    07:07:09 saltbot>   help               Display this message
    07:07:09 saltbot>   say <message>      Says <message> on IRC
    07:07:09 saltbot>   highstate <target> [expr_form] [wait_gitfs]
    07:07:09 saltbot>   reload <module>    Reloads <module>, one of:
    07:07:10 saltbot>     config, webapp, ircbot, exchange, saltshaker
    07:07:15 adamgreig> reload webapp
    07:07:17 saltbot> Reloading webapp

    10:42:26 saltbot> Push to ukhas/habhub-homepage master by adamgreig, highstating glob adamscratch.habhub.org
    10:42:27 saltbot> Salt 20150118104539540662 started to highstate adamscratch.habhub.org                     
    10:42:27 saltbot> http://saltbot.habhub.org/jobs/20150118104539540662                                       
    10:42:40 saltbot> Salt JID 20150118104539540662 finished, all OK                                            


## Configuration

By default all configuration is in `saltbot.yml`, though you may specify a
different file as the only command-line argument to `saltbot`. The config file
is in YAML and contains comments on how to set it up.
