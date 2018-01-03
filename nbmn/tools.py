#!/usr/bin/env python

"""
Nutbush Movie Night tools script.

Run this script via the bash script ./tool in the root of this project

All the tools in the file assume they are being run in the root directory of
the project (but note that we import nbmn via relative imports since we are
part of the package).
"""

# pylama:ignore=E501,D204,D212

import sys
import os
import subprocess
import argparse
from contextlib import contextmanager

from gludb.config import class_database, Database
from gludb.simple import DBObject

from .model import Movie, Night, Attendee
from .imdb import norm_imdbid

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


def command(need_db=False):
    """Decorator for capturing commands."""
    def dec(f):
        COMMANDS[f.__name__] = (f, need_db)
        return f
    return dec


def usage(msg=''):
    """Display usage for our script."""
    if msg:
        print(msg)
    print('tools <cmd> [options related to cmd]')
    print('Run "tools help" for details')
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


@command(need_db=False)
def help(opts):
    """Print out documentation."""
    usage('Helping!')
    print('')

    def line(cmd, ndb, descrip):
        print('%-12s %-8s   %s' % (cmd, ndb, descrip))

    line('Command', 'NeedDB', 'Description')
    line('-------', '------', '-----------')
    for name, (func, need_db) in sorted(COMMANDS.items()):
        line(name, need_db, func.__doc__)
    return 0


@command(need_db=False)
def test(opts):
    """Execute unit tests."""
    import nose
    nose.main(argv=['nosetests'] + opts)


@command(need_db=False)
def run(opts):
    """Execute ./run script - just for debugging."""
    return subprocess.run(['./run'] + opts).returncode


@command(need_db=False)
def testrun(opts):
    """Execute ./run script using test/test.config as the main config."""
    with env_var('NBMN_CONFIG', os.path.abspath('./test/test.config')):
        return subprocess.run(['./run'] + opts).returncode


@command(need_db=True)
def list_routes(opts):
    """Attempt to list all routes in the app."""
    data = sorted(_find_routes())

    widths = [len(i) for i in data[0]]
    for d in data[1:]:
        for i, w in enumerate(len(i) for i in d):
            if w > widths[i]:
                widths[i] = w

    def _fixout(width, txt, suffix=' '):
        pad = ' ' * (width+1)
        s = txt + pad
        sys.stdout.write(s[:width])
        sys.stdout.write(suffix)

    ew, mw, uw = widths
    for endpoint, methods, url in data:
        _fixout(mw, methods)
        _fixout(ew, endpoint)
        _fixout(uw, url, suffix='\n')
    sys.stdout.flush()


def _find_routes():
    from main import app
    SKIPS = {'HEAD', 'OPTIONS'}
    print('METHODS SKIPPED: {}'.format(SKIPS))
    for rule in app.url_map.iter_rules():
        methods = ','.join(m for m in rule.methods if m not in SKIPS)
        yield (rule.endpoint, methods, rule.rule)


@command(need_db=True)
def fixmovies(opts):
    """Re-query remote sources for every movie in the DB."""
    movies = set([''])  # Will remove empty string when done

    print('Scanning Nights...')
    for night in Night.find_all():
        movies.add(norm_imdbid(night.imdbid))

    print('Scanning Movies...')
    for movie in Movie.find_all():
        movies.add(norm_imdbid(movie.imdbid))

    movies.remove('')  # as promised
    print("...Found %d unique movie ID's" % len(movies))

    for imdbid in movies:
        movie = Movie.find_by_imdb(imdbid, force=True)
        print('Searched %s: Found %s => %s' % (imdbid, movie.imdbid, movie.name))

    print('Finished.')


@command(need_db=True)
def fixpeeps(opts):
    """Create any necessary Attendee records using current.config."""
    print('Scanning Nights...')
    night_count = 0
    attendees = set()
    for night in Night.find_all():
        attendees.update(night.attendees)
        night_count += 1
    print('...Found %d attendees in %d nights' % (len(attendees), night_count))

    print('Scanning Attendee...')
    existing = set([a.name for a in Attendee.find_all()])
    missing = attendees - existing
    print('...Found %d attendees - need %d' % (len(existing), len(missing)))

    for name in missing:
        print('Creating:' + name)
        Attendee(name=name).save()

    print('Finished.')


@command(need_db=True)
def orphanmovies(opts):
    """Find all movies that are not attached to a Movie Night."""
    parser = argparse.ArgumentParser(description=orphanmovies.__doc__)
    parser.add_argument('--delete', default=False, action='store_true', help='Delete orphans')
    parser.add_argument('--verbose', default=False, action='store_true', help='Output full orphan output')
    args = parser.parse_args(opts)

    def delete_movie(movie):
        if args.delete:
            movie.delete()
            print('DELETED!')

    def orphan_text(movie):
        if args.verbose:
            return movie.to_data()
        else:
            return '[%s]:%s' % (norm_imdbid(movie.imdbid), movie.name)

    print('Scanning Nights...')
    night_movies = set()
    night_count = 0
    for night in Night.find_all():
        night_count += 1
        imdbid = norm_imdbid(night.imdbid)
        if imdbid:
            night_movies.add(imdbid)
    print("...Found %d IMDB ID's in %d nights" % (len(night_movies), night_count))

    print('Scanning Movies...')
    orphan_count = 0
    for movie in Movie.find_all():
        imdbid = norm_imdbid(movie.imdbid)
        if imdbid in night_movies:
            continue

        orphan_count += 1
        print('ORPHAN: %s' % orphan_text(movie))
        delete_movie(movie)
    print('...Found %d orphan movies' % orphan_count)

    print('Finished.')


# IMPORTANT: handlers calling this function must have need_db=True in their
# command decorator
def alternate_copy(glu_database, log_file):
    """Copy all data to the alternate gludb database location."""
    print('Configuring logging to use %s' % log_file)
    import logging
    import daiquiri
    daiquiri.setup(
        level=logging.DEBUG,
        outputs=(
            daiquiri.output.File(log_file, level=logging.DEBUG),
            daiquiri.output.Stream(sys.stdout, level=logging.WARN),
        )
    )
    log = daiquiri.getLogger('nbmn-tools')

    class_database(AttendeeOutput, glu_database)
    class_database(MovieOutput, glu_database)
    class_database(NightOutput, glu_database)
    log.warn('Creating output tables...')
    AttendeeOutput.ensure_table()
    NightOutput.ensure_table()
    MovieOutput.ensure_table()

    def xfer(name, in_table, out_table):
        log.warn('Transferring %s...' % name)
        count = 0
        for record in in_table.find_all():
            out_table.from_data(record.to_data()).save()
            count += 1
        log.warn('...Saved %d' % count)

    xfer('attendees', Attendee, AttendeeOutput)
    xfer('nights', Night, NightOutput)
    xfer('movies', Movie, MovieOutput)
    log.warn('Finished.')


@command(need_db=True)
def postgre(opts):
    """Read movies and nights using current.config and write to postgresql."""
    if len(opts) < 1:
        print('Submit the connection string on the command line, please. Ex:')
        print("host='localhost' dbname='test' user='test' password='somepasswd'")
        return
    conn_string = ' '.join(opts)
    print('Using conn str: %s' % conn_string)

    tables = [NightOutput, MovieOutput, AttendeeOutput]
    table_names = [t.get_table_name() for t in tables]

    print('Dropping postgresql tables...')
    import psycopg2
    with psycopg2.connect(conn_string) as conn:
        with conn.cursor() as cur:
            for tabname in table_names:
                print('Dropping %s' % tabname)
                cur.execute('drop table if exists ' + tabname)

    alternate_copy(
        Database('postgresql', conn_string=conn_string),
        'postgresql-import.log'
    )


@command(need_db=True)
def export(opts):
    """Read all major data into specified sqlite database file."""
    if len(opts) != 1:
        print('Command line should be the target file name')
        return
    out_filename = opts[0]
    print('Using output file: %s' % out_filename)

    alternate_copy(
        Database('sqlite', filename=out_filename),
        'sqlite-export.log'
    )


def main():
    """Entry point."""
    args = sys.argv[1:]
    if len(args) < 1:
        print('No command specified: showing help')
        cmd, opts = 'help', []
    else:
        cmd, opts = args[0], args[1:]

    cmd_func, need_db = COMMANDS.get(cmd, (None, None))
    if not cmd_func:
        return usage('Unknown cmd ' + cmd)

    # Super simple
    if not need_db:
        return cmd_func(opts)

    # Set up main db and app context with a set config
    with env_var('NBMN_CONFIG', os.path.abspath('./current.config')):
        import main
        main.database_config()
        with main.app.app_context():
            return cmd_func(opts)


if __name__ == '__main__':
    sys.exit(main() or 0)
