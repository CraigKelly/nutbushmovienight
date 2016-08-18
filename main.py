#!/usr/bin/env python

"""Nutbush Movie Night web app.

This is the main entry point for the web app. The actual functionality is in
the nbmn package. See utest for unit testing and test for functional test
setup.
"""

# pylama:ignore=E501

# TODO: allow image uploads and usage with our ckeditor

# TODO: full text search with a mongo text index *or something*


import os
import logging
from datetime import datetime

from flask import Flask, g

from gludb.config import default_database, Database

from nbmn.log import app_logger
from nbmn.model import User, Movie, Night, Attendee
from nbmn.auth import auth
from nbmn.main_app import main
from nbmn.data import data
from nbmn.lawyer import lawyer

import nbmn.remote

# Create app and handle configuration
app = Flask(__name__)
app.config.from_pyfile('default.config')
app.config.from_envvar('NBMN_CONFIG', silent=False)
app.secret_key = app.config.get('FLASK_SECRET', None)

# Update any downstream config variables
nbmn.remote.MATER_API_KEY = app.config.get('MATER_API_KEY', '')

# Handle debug flag from config file - and let them use anything truthy to
# our DEBUG flag
app.debug = True if app.config.get('DEBUG', None) else False

# Set up logging
if app.debug:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)
app_logger().info('Application logging begin: debug==%s', app.debug)

# They can specify that certain config variables are copied in to
# the system environment
for name in app.config.get("ENV_POPULATE"):
    val = str(app.config.get(name))
    app_logger().info('Setting env[%s]=%s' % (name, val))
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
    # Copy some config settings in to the g object for other uses (like our
    # template dict helpers in helpers.py). Note that we hard-code fallbacks
    # just in case
    setattr(g, 'DEFAULT_BS_THEME', app.config.get('DEFAULT_BS_THEME', 'darkly'))
    setattr(g, 'DEFAULT_JQUI_THEME', app.config.get('DEFAULT_JQUI_THEME', 'vader'))
    setattr(g, 'year', datetime.now().year)


def database_config():
    """Set up the database using app.config."""
    backend = app.config["DB_BACKEND"]
    if not backend:
        raise ValueError('No database backend specified')

    # We actually monkey-patch and log saves to the database if required
    if app.config["LOG_SAVES"]:
        app_logger().info("Monkey-patching gludb to log object saves")
        Database._old_save = Database.save

        def logged_save(self, obj):
            self._old_save(obj)
            app_logger().info("%s[id=%s] Saved:%s", obj.get_table_name(), obj.get_id(), obj.to_data())

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
    Night.ensure_table()
    Attendee.ensure_table()
    Attendee.ensure_attendees()


def main():
    """Entry point."""
    HOST = app.config['HOST']
    PORT = app.config['PORT']
    BANNER = app.config['BANNER']

    # The banner is printed - NOT logged
    if BANNER:
        print(('*' * 75))
        print(BANNER)
        print(('*' * 75))

    database_config()

    app_logger().info("About to start serving on %s:%d", HOST or "[ALL IFaces]", PORT)
    from waitress import serve
    serve(app, host=HOST, port=PORT)

if __name__ == '__main__':
    main()
