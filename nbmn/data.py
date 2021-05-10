"""data - the data/exploration for Nutbush Movie Night."""

# pylama:ignore=E501

import json

from operator import attrgetter

from flask import Blueprint, jsonify, make_response, render_template, request, url_for

from .atom import AtomFeed
from .utils import templated, use_error_page
from .model import Night, Movie, Attendee


data = Blueprint('data', __name__)


def _to_dict(obj):
    return json.loads(obj.to_data())


def _movie_dict(movie):
    d = _to_dict(movie)
    d['extdata']['Poster'] = f'https://nutbushposters.fly.dev/{movie.imdbid}'
    return d


@data.route('/gimme')
def data_dump():
    """Return all night/movie data in JSON format for client-side analysis."""
    return jsonify({
        'attendees': [_to_dict(a) for a in Attendee.find_all()],
        'nights': [_to_dict(n) for n in Night.find_all()],
        'movies': dict([(m.imdbid, _movie_dict(m)) for m in Movie.find_all()]),
    })


@data.route('/explore')
@templated('explore.html')
@use_error_page
def explore_data():
    """Our data exploration and search page."""
    return {}


@data.route('/nights.atom')
def atom_nights():
    feed = AtomFeed(
        title='Nutbush Movie Night',
        title_type='text',
        subtitle='All Movie Nights',
        author=sorted(Attendee.OLIGARCHS),
        feed_url=request.url, # TODO: replace http: with https:
        url=request.url_root,
        logo=url_for('static', filename='logo.png'),
    )

    nights = Night.find_all()
    nights.sort(key=attrgetter('datestr'), reverse=True)

    for night in nights:
        dt = Night.date_from_str(night.datestr)
        night_title = 'Movie Night {} ({})'.format(night.listdate, night.moviename)
        night_text = render_template('night.atom.html', night_title=night_title, night=night, dt=dt)

        feed.add(
            title=night_title,
            title_type='text',
            content=night_text,
            content_type='html',
            url=url_for('main.night_display', datestr=night.datestr),
            updated=dt,
            published=dt
        )

    return feed.get_response()


def _line_folder(src):
    """Handle line folding and termination for iCalendar."""
    for line in src:
        while len(line) > 75:
            chunk, line = line[:73], line[73:]
            yield chunk + '\r\n\t'
        if line:
            yield line + '\r\n'


def _ical_attendee(att):
    """Given one of our attendee's, return an iCal comptible string usable by Google Calendar."""
    return 'ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=ACCEPTED;CN={n:s};X-NUM-GUESTS=0:mailto:{em:s}@nutbushmovienight.com'.format(n=att.title(), em=att.lower())


@data.route('/calendar')
def calendar():
    cal_lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Wondrous Oligarchs of Nutbush//NONSGML nutbushmovienight.com//EN'
    ]

    for night in Night.find_all():
        one = [
            'BEGIN:VEVENT',
            'UID:{}.{}@nutbushmovienight.com'.format(night.datestr, night.id),
            'DTSTAMP:' + night.dstamp_ical,
            'DTSTART:' + night.listdate_ical,
            'SUMMARY:{} ({})'.format(night.moviename, night.dinner)
        ]
        one.extend([_ical_attendee(a) for a in night.attendees])
        one.append('END:VEVENT')

        cal_lines.extend(one)

    cal_lines.append('END:VCALENDAR')

    resp = make_response(''.join(_line_folder(cal_lines)))
    resp.mimetype = 'text/calendar'
    resp.headers['Content-Disposition'] = 'attachment; filename=calendar.ics'

    return resp
