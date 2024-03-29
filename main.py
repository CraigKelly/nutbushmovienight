#!/usr/bin/env python

"""
Nutbush Movie Night web app.

This is the main entry point for the web app. The actual functionality is in
the nbmn package. See utest for unit testing and test for functional test
setup.
"""

# pylama:ignore=E501,D212

# TODO: see deployment.md - need to switch our server deployment
import socket
import requests.packages.urllib3.util.connection as urllib3_cn


def allowed_gai_family():
    return socket.AF_INET

urllib3_cn.allowed_gai_family = allowed_gai_family

import os
import logging
from datetime import datetime

from flask import Flask, g

from gludb.config import default_database, Database

import nbmn.log as log

from nbmn.model import User, Movie, Night, Attendee, MovieOverride
from nbmn.auth import auth
from nbmn.main_app import main
from nbmn.data import data
from nbmn.lawyer import lawyer

app = Flask(__name__)

# Create app and handle configuration
app = Flask(__name__)
app.config.from_pyfile('default.config')
app.config.from_envvar('NBMN_CONFIG', silent=False)
app.secret_key = app.config.get('FLASK_SECRET', None)

# Handle debug flag from config file - and let them use anything truthy to
# our DEBUG flag
app.debug = True if app.config.get('DEBUG', None) else False

# Set up logging
log.setup(level=logging.DEBUG if app.debug else logging.INFO)
log.app_logger().info('Application logging begin: debug==%s', app.debug)

# They can specify that certain config variables are copied in to
# the system environment
for name in app.config.get("ENV_POPULATE"):
    val = str(app.config.get(name))
    log.app_logger().info('Setting env[%s]=%s' % (name, val))
    os.environ[name] = val

# Now that we're all set up, we can register our blueprints
app.register_blueprint(auth)
app.register_blueprint(main)
app.register_blueprint(data)
app.register_blueprint(lawyer)


# Pre-request setup for all requests... currently just setting some values on g
@app.before_request
def setup():
    """One-time setup work."""
    now = datetime.now()
    # Current year is mainly for our copyright message
    setattr(g, 'year', now.year)
    # Current timestamp is useful for lots of stuff
    setattr(g, 'timestamp', int(now.timestamp()))


def database_config():
    """Set up the database using app.config."""
    backend = app.config["DB_BACKEND"]
    if not backend:
        raise ValueError('No database backend specified')

    # We actually monkey-patch and log saves to the database if required
    if app.config["LOG_SAVES"]:
        log.app_logger().info("Monkey-patching gludb to log object saves")
        Database._old_save = Database.save

        def logged_save(self, obj):
            self._old_save(obj)
            log.app_logger().info("%s[id=%s] Saved:%s", obj.get_table_name(), obj.get_id(), obj.to_data())

        Database.save = logged_save

    # Certain backends need to read certain config variables for DB paramters
    params = dict()

    if backend == 'sqlite':
        params['filename'] = app.config["SQLITE_FILENAME"]
        if not params['filename']:
            raise ValueError("Backend sqlite specified, but no SQLITE_FILENAME given")
    elif backend == 'mongodb':
        params['mongo_url'] = app.config["MONGODB_URL"]
        if not params['mongo_url']:
            raise ValueError("Backend mongodb specified, but no MONGODB_URL given")

    db_config = Database(backend, **params)

    default_database(db_config)
    User.ensure_table()
    Movie.ensure_table()
    MovieOverride.ensure_table()
    Night.ensure_table()
    Attendee.ensure_table()
    Attendee.ensure_attendees()


def main():
    """Entry point."""
    HOST = app.config['HOST'] or '0.0.0.0'
    PORT = app.config['PORT']
    BANNER = app.config['BANNER']

    # The banner is printed - NOT logged
    if BANNER:
        print(('*' * 75))
        print(BANNER)
        print(('*' * 75))

    database_config()

    log.app_logger().info("About to start serving on %s:%d", HOST or "[ALL IFaces]", PORT)
    from waitress import serve
    serve(app, host=HOST, port=PORT)


if __name__ == '__main__':
    main()
    logging.shutdown()
