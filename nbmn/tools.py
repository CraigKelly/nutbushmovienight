#!/usr/bin/env python

"""Nutbush Movie Night tools script.

Run this script via the bash script ./tool in the root of this project

All the tools in the file assume they are being run in the root directory of
the project (but note that we import nbmn via relative imports since we are
part of the package).
"""

# pylama:ignore=E501,D204

import sys
import os
import subprocess
from contextlib import contextmanager

from gludb.config import class_database, Database
from gludb.simple import DBObject

from .model import Movie, Night, Attendee
from .remote import norm_imdbid

COMMANDS = dict()


@contextmanager
def env_var(key, value):
    """Set env key to value and resets when with block ends."""
    old_val = os.environ.get(key, None)
    os.environ[key] = value
    yield
    if old_val is None:
        del os.environ[key]
    else:
        os.environ[key] = old_val


def command(f):
    """Decorator for capturing commands."""
    COMMANDS[f.__name__] = f
    return f


def usage(msg=""):
    """Display usage for our script."""
    if msg:
        print(msg)
    print("tools <cmd> [options related to cmd]")
    print("Run 'tools help' for details")
    return 1


@DBObject(table_name='Nights')
class NightOutput(Night):
    """Used for writing to alternate data location."""
    pass


@DBObject(table_name='Movies')
class MovieOutput(Movie):
    """Used for writing to alternate data location."""
    pass


@DBObject(table_name='Attendees')
class AttendeeOutput(Attendee):
    """Used for writing to alternate data location."""
    pass


@command
def help(opts):
    """Print out documentation."""
    usage("Helping!")
    print("")

    def line(cmd, descrip):
        print("%-10s   %s" % (cmd, descrip))

    line("Command", "Description")
    line("-------", "-----------")
    for name, func in sorted(COMMANDS.items()):
        line(name, func.__doc__)
    return 0


@command
def test(opts):
    """Execute unit tests."""
    import nose
    nose.main(argv=['nosetests'] + opts)


@command
def run(opts):
    """Execute ./run script - just for debugging."""
    return subprocess.run(["./run"] + opts).returncode


@command
def testrun(opts):
    """Execute ./run script using test/test.config as the main config."""
    # env = os.environ.copy()
    # env['NBMN_CONFIG'] = os.path.abspath('./test/test.config')
    with env_var('NBMN_CONFIG', os.path.abspath('./test/test.config')):
        return subprocess.run(["./run"] + opts).returncode


@command
def fixmovies(opts):
    """Re-query remote sources for every movie in the DB."""
    print("Configuring database backend")
    with env_var('NBMN_CONFIG', os.path.abspath('./current.config')):
        import main
        main.database_config()
        movies = set()

        print("Scanning Nights...")
        for night in Night.find_all():
            movies.add(norm_imdbid(night.imdb))

        print("Scanning Movies...")
        for movie in Movie.find_all():
            movies.add(norm_imdbid(movie.imdb))

        print("...Found %d unique movie ID's" % len(movies))

        for imdbid in movies:
            pass  # TODO: actual work

    print("Finished.")


@command
def fixpeeps(opts):
    """Create any necessary Attendee records using current.config."""
    print("Configuring database backend")
    with env_var('NBMN_CONFIG', os.path.abspath('./current.config')):
        import main
        main.database_config()
        print("Scanning Nights...")
        night_count = 0
        attendees = set()
        for night in Night.find_all():
            attendees.update(night.attendees)
            night_count += 1
        print("...Found %d attendees in %d nights" % (len(attendees), night_count))

        print("Scanning Attendee...")
        existing = set([a.name for a in Attendee.find_all()])
        missing = attendees - existing
        print("...Found %d attendees - need %d" % (len(existing), len(missing)))

        for name in missing:
            print("Creating:" + name)
            Attendee(name=name).save()
    print("Finished.")


def alternate_copy(glu_database, log_file):
    """Copy all data to the alternate gludb database location."""
    print("Configuring logging to use %s" % log_file)
    import logging
    logging.basicConfig(level=logging.DEBUG, filename=log_file)
    stdout_handler = logging.StreamHandler()
    stdout_handler.setLevel(logging.WARN)
    log = logging.getLogger()
    log.addHandler(stdout_handler)

    with env_var('NBMN_CONFIG', os.path.abspath('./current.config')):
        log.warn("Starting main database config")
        import main
        main.database_config()

        class_database(AttendeeOutput, glu_database)
        class_database(MovieOutput, glu_database)
        class_database(NightOutput, glu_database)
        log.warn("Creating output tables...")
        AttendeeOutput.ensure_table()
        NightOutput.ensure_table()
        MovieOutput.ensure_table()

        def xfer(name, in_table, out_table):
            log.warn("Transferring %s..." % name)
            count = 0
            for record in in_table.find_all():
                out_table.from_data(record.to_data()).save()
                count += 1
            log.warn("...Saved %d" % count)

        xfer("attendees", Attendee, AttendeeOutput)
        xfer("nights", Night, NightOutput)
        xfer("movies", Movie, MovieOutput)
        log.warn("Finished.")


@command
def postgre(opts):
    """Read movies and nights using current.config and write to postgresql."""
    if len(opts) < 1:
        print("Submit the connection string on the command line, please. Ex:")
        print("host='localhost' dbname='test' user='test' password='somepasswd'")
        return
    conn_string = ' '.join(opts)
    print("Using conn str: %s" % conn_string)

    print("Dropping postgresql tables...")
    import psycopg2
    with psycopg2.connect(conn_string) as conn:
        with conn.cursor() as cur:
            print("Dropping %s", NightOutput.get_table_name())
            cur.execute("drop table if exists " + NightOutput.get_table_name())
            print("Dropping %s", MovieOutput.get_table_name())
            cur.execute("drop table if exists " + MovieOutput.get_table_name())
            print("Dropping %s", AttendeeOutput.get_table_name())
            cur.execute("drop table if exists " + AttendeeOutput.get_table_name())

    alternate_copy(
        Database("postgresql", conn_string=conn_string),
        "postgresql-import.log"
    )


@command
def export(opts):
    """Read all major data into specified sqlite database file."""
    if len(opts) != 1:
        print("Command line should be the target file name")
        return
    out_filename = opts[0]
    print("Using output file: %s" % out_filename)

    alternate_copy(
        Database("sqlite", filename=out_filename),
        "sqlite-export.log"
    )


def main():
    """Entry point."""
    args = sys.argv[1:]
    if len(args) < 1:
        return usage("No command specified")

    cmd, opts = args[0], args[1:]
    cmd_func = COMMANDS.get(cmd, None)
    if not cmd_func:
        return usage("Unknown cmd " + cmd)

    return cmd_func(opts)

if __name__ == '__main__':
    sys.exit(main() or 0)
