#!/usr/bin/env python

"""
Nutbush Movie Night web app.

This is the main entry point for the web app. The actual functionality is in
the nbmn package. See utest for unit testing and test for functional test
setup.
"""

# pylama:ignore=E501,D212

# TODO: switch from DataTables to FooTable (http://fooplugins.github.io/FooTable/docs/getting-started.html)

# TODO: see about using daiquiri for logging: be sure to log at tools

# TODO: allow link selection from nbmn flickr account...
# We would get the images using a call to flickr.people.getPublicPhotos for 65666367@N06
# (see https://www.flickr.com/services/api/explore/flickr.people.getPublicPhotos)
#
# For each entry we would construct an image link with the pattern
# https://farm{farm-id}.staticflickr.com/{server-id}/{id}_{secret}_[mstzb].jpg where
#
# m - small
# s - super small (smaller than thumbnail)
# t - thumbnail
# z - medium
# b - large


import os
import logging
from datetime import datetime

from flask import Flask, g

from gludb.config import default_database, Database

from nbmn.log import app_logger
from nbmn.model import User, Movie, Night, Attendee, MovieOverride
from nbmn.auth import auth
from nbmn.main_app import main
from nbmn.data import data
from nbmn.lawyer import lawyer

# Create app and handle configuration
app = Flask(__name__)
app.config.from_pyfile('default.config')
app.config.from_envvar('NBMN_CONFIG', silent=False)
app.secret_key = app.config.get('FLASK_SECRET', None)

# Handle debug flag from config file - and let them use anything truthy to
# our DEBUG flag
app.debug = True if app.config.get('DEBUG', None) else False

# Set up logging
LOG_LEVEL = logging.DEBUG if app.debug else logging.INFO
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s %(message)s')
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

    app_logger().info("About to start serving on %s:%d", HOST or "[ALL IFaces]", PORT)
    from waitress import serve
    serve(app, host=HOST, port=PORT)


if __name__ == '__main__':
    main()
    logging.shutdown()
