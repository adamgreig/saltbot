# Saltbot
An IRC bot for [Salt](http://www.saltstack.com/community/) deployments.

## Install

Currently requires Python 3.4.

    $ git clone https://github.com/adamgreig/saltbot.git
    $ cd saltbot
    saltbot$ virtualenv venv
    saltbot$ source venv/bin/activate
    saltbot$ pip install -r requirements.txt
    saltbot$ python setup.py develop
    saltbot$ cp saltbot.yml.sample saltbot.yml
    saltbot$ vi saltbot.yml

## Usage

    saltbot$ saltbot
    [2015-01-08 06:46:33,346] INFO saltbot: Loading config
    [2015-01-08 06:46:33,350] INFO saltbot: Saltbot starting up
    [2015-01-08 06:46:33,356] INFO saltbot.exchange: Exchange started
    saltbot command console
    commands:
      quit               Closes saltbot
      help               Display this message
      say <message>      Says <message> on IRC
      reload <module>    Reloads <module>, one of:
         webapp, ircbot, exchange, saltshaker
    [2015-01-08 06:46:33,358] INFO saltbot.http: App starting up
    [2015-01-08 06:46:33,358] INFO saltbot.ircbot: Connecting to server
    [2015-01-08 06:46:39,655] INFO saltbot.ircbot: Welcome message received, joining channel
    [2015-01-08 06:46:46,385] INFO saltbot.ircbot: Joined channel #saltbot
    > say hi
    Saying hi
    > reload webapp
    Reloading webapp

## Configuration

By default all configuration is in `saltbot.yml`, though you may specify a
different file as the only command-line argument to `saltbot`. The config file
is in YAML and should be self explanatory.
