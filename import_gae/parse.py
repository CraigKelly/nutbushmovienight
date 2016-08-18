#!/usr/bin/env python3

"""Parsing logic for data retrieved from GAE via retrieve.py."""

# pylama:ignore=E501,C901

from datetime import datetime
import json

from gludb.config import default_database, Database
from nbmn.model import User, Movie, Night, Attendee
from nbmn.remote import norm_imdbid


def _save_maters(movies, do_insert):
    if do_insert:
        print("Inserting %d movies..." % len(movies))
        for movie in movies:
            movie.save()
    else:
        print("Insert off - would have inserted %d movies..." % len(movies))
    print("...Done")


def maters(data, do_insert=True):
    """rotten tomatoes movie data dump."""
    if len(Movie.find_all()):
        raise ValueError('You must clear out all previous data before running this import')

    print(("Maters Count: %d" % len(data)))

    title_ref = dict()
    movies = []

    print("Performing scan...")
    for key, val in data.items():
        # Some handy extraction
        imdbid = norm_imdbid(key)
        ts = val["update_time"]
        imdb = val.get("imdb", dict())
        rottom = val.get("rottom", dict())

        title = str(imdb.get('title', '')).strip()
        if not title:
            print('Found no title for %s' % imdbid)
            raise ValueError('Invalid! No title specified!')
        if imdbid in title_ref:
            print('Duplicate IMDB ID [%s]! First was "%s", just found "%s"' % (
                imdbid, title_ref[imdbid], title
            ))
        else:
            title_ref[imdbid] = title

        # Check for weird director issue from one of our data sources
        dirs = imdb.get('abridged_directors', list())
        dirmod = False
        for idx in range(len(dirs)):  # We modify the array
            # Remember - we're Python 3 *only*
            d = dirs[idx]
            if isinstance(d, str):
                dirs[idx] = dict(name=d)
                dirmod = True
        if dirmod:
            print('Director update for %s: %s' % (imdbid, repr(dirs)))
            imdb['abridged_directors'] = dirs
            data[key]['imdb'] = imdb

        # print(("%-10s [%s] imdb: %6d rottom %6d" % (imdbid, ts, len(imdb), len(rottom))))
        movie = Movie(
            name=title,
            imdbid=imdbid,
            extdata=dict(imdb=imdb, rottom=rottom, update_time=ts)
        )
        movies.append(movie)

    _save_maters(movies, do_insert)
    return title_ref


def _validate_night(night, title_ref):
    # We assume that datestr is already correct
    if not night.moviename:
        raise ValueError('Missing movie name for ' + night.datestr)

    ref_name = title_ref.get(night.imdbid, '')
    if not ref_name:
        print('Warning: movie night %s has unknown IMDB ID %s' % (night.datestr, night.imdbid))
    elif ref_name.lower() != night.moviename.lower():
        print('Warning-name-mismatch: imdb="%s", movierec="%s"' % (ref_name, night.moviename))

    uniqattend = set(night.attendees)
    if len(uniqattend) < 2 or 'Marty' not in uniqattend or 'Adam' not in uniqattend:
        raise ValueError('Invalid attendee list for ' + night.datestr)


def _write_nights(nights, do_insert):
    if do_insert:
        print('No errors found - will insert %d nights...' % len(nights))
        for night in nights:
            night.save()
    else:
        print('Insert turned off - skipping insert for %d nights' % len(nights))
    print('...Done')


def _create_attendees(attendees, do_insert):
    current_attendees = set([a.name for a in Attendee.find_all()])
    missing_attendees = attendees - current_attendees
    if do_insert:
        print("Will now insert %d attendees..." % len(missing_attendees))
        for a in missing_attendees:
            Attendee(name=a).save()
    else:
        print("Insert off - would have created attendees: %s" % (repr(missing_attendees),))


def nights(data, title_ref, do_insert=False):
    """movie night data dump."""
    if do_insert:
        if len(Night.find_all()):
            raise ValueError('You must clear out all previous data before running this import')
    else:
        print('No inserts for Nights - skipping empty BD check')

    print(("Nights Count: %d" % len(data)))

    nowyr = datetime.now().year
    nights = []
    all_attendees = set()

    for datum in data:
        night_date_str = datum.get('night_date', '')
        if not night_date_str:
            raise ValueError('No date for movie night')
        night_date = datetime.strptime(night_date_str, "%b %d, %Y")
        if night_date.year < 2001 or night_date.year > nowyr:
            raise ValueError('Invalid date: ' + night_date_str)

        moviename = datum.get('moviename', '')
        imdbid = norm_imdbid(datum.get('imdbid', ''))
        if not imdbid:
            print('Warning (not error) - no IMDB ID for movie night: %s - %s' % (night_date_str, moviename))

        night = Night(
            datestr=night_date,
            imdbid=norm_imdbid(datum.get('imdbid', '')),
            moviename=moviename,
            dinner=datum.get('dinner', ''),
            comments=datum.get('comments', ''),
            attendees=list(set(datum.get('attendees', list()))),
        )
        _validate_night(night, title_ref)
        nights.append(night)
        all_attendees.update(set(night.attendees))

    _write_nights(nights, do_insert)
    _create_attendees(all_attendees, do_insert)

    print('...Done')


def main():
    """Run all parsing on gimme.json."""
    import sys
    do_insert = None
    db_target = None
    for a in sys.argv[1:]:
        if a == '--no-insert':
            do_insert = False
        elif a == '--insert':
            do_insert = True
        elif a == '--sqlite':
            db_target = 'sqlite'
        elif a == '--mongo':
            db_target = 'mongo'
        else:
            raise ValueError('Unknown parameter: ' + a)

    if do_insert is None:
        raise ValueError('You must either pass --insert or --no-insert')
    if db_target is None:
        raise ValueError('You must either pass --sqlite or --mongo')

    if db_target == "sqlite":
        db = Database('sqlite', filename='../.testingdb.sqlite')
    elif db_target == "mongo":
        db = Database('mongodb', mongo_url='mongodb://localhost:27017/nbmn')
    else:
        raise ValueError("Unknown DB Target!")
    default_database(db)

    print('Ensuring db is set up')
    User.ensure_table()
    Movie.ensure_table()
    Night.ensure_table()
    Attendee.ensure_table()
    Attendee.ensure_attendees()

    all = json.loads(open("gimme.json").read())
    print(("All Keys: %s" % str(list(all.keys()))))
    title_ref = maters(all.get("maters", {}), do_insert=do_insert)
    nights(all.get("nights", {}), title_ref, do_insert=do_insert)

if __name__ == "__main__":
    main()
