"""data - the data/exploration for Nutbush Movie Night."""

# pylama:ignore=E501

import json

from flask import Blueprint, jsonify

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
