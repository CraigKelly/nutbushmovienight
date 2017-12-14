"""data - the data/exploration for Nutbush Movie Night."""

# pylama:ignore=E501

import json

from operator import attrgetter

from flask import Blueprint, jsonify, render_template, request, url_for

import werkzeug.contrib.atom as atom

from .utils import templated, use_error_page
from .model import Night, Movie, Attendee


data = Blueprint('data', __name__)


def _to_dict(obj):
    return json.loads(obj.to_data())


@data.route('/gimme')
def data_dump():
    """Return all night/movie data in JSON format for client-side analysis."""
    return jsonify({
        'attendees': [_to_dict(a) for a in Attendee.find_all()],
        'nights': [_to_dict(n) for n in Night.find_all()],
        'movies': dict([(m.imdbid, _to_dict(m)) for m in Movie.find_all()]),
    })


@data.route('/explore')
@templated("explore.html")
@use_error_page
def explore_data():
    """Our data exploration and search page."""
    return {}


@data.route('/nights.atom')
def atom_nights():
    feed = atom.AtomFeed(
        title='Nutbush Movie Night',
        title_type='text',
        subtitle='All Movie Nights',
        author=sorted(Attendee.OLIGARCHS),
        feed_url=request.url, 
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
