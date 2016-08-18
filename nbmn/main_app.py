"""main_app - the main functionality for Nutbush Movie Night."""

# pylama:ignore=E501

from os.path import isfile
from datetime import datetime
from operator import attrgetter

from flask import (
    abort,
    Blueprint,
    flash,
    jsonify,
    redirect,
    request,
    url_for
)

from .log import app_logger
from .auth import NotAuthorized, require_login
from .utils import logged_errors, template, templated, use_error_page, project_file
from .model import User, Movie, Night, Attendee


main = Blueprint('main', __name__)


@main.route('/')
@templated("base.html")
@use_error_page
def main_page():
    """Default page for app."""
    MAX_NIGHTS = 12
    nights = Night.find_by_index('index_year', datetime.now().year)
    if len(nights) < MAX_NIGHTS:
        nights.extend(Night.find_by_index('index_year', datetime.now().year - 1))
    nights.sort(key=attrgetter('datestr'), reverse=True)

    for night in nights:
        thumb = None
        movie = Movie.find_by_imdb(night.imdbid)
        if movie and movie.extdata:
            imglist = movie.extdata.get('imdb', {}).get('posters', {})
            for tag in ["thumbnail", "profile", "detailed", "original"]:
                thumb = imglist.get(tag, None)
                if thumb and thumb != "N/A":
                    break
        night.thumb = thumb or "/static/default_movie_thumb.png"

    return {
        'movienights': nights[:MAX_NIGHTS]
    }


@main.route('/movie')
@main.route('/movie/<moviekey>')
@templated("movie.html")
@use_error_page
def movie_display(moviekey=None):
    """Display 1 or all movies."""
    def fixup(movie):
        if not movie:
            return None
        movie.urlname = movie.imdbid
        return movie

    if moviekey:
        movie = Movie.find_by_imdb(moviekey)
        return {'movie': fixup(movie), 'movie_name': movie.name or '???'}
    else:
        movies = [fixup(m) for m in Movie.find_all()]
        movies.sort(key=attrgetter('name'))
        return {'movies': movies, 'movie_name': 'ALL'}


@main.route('/moviemater/<materkey>')
@logged_errors
def movie_mater(materkey):
    """Movie lookup via mater API."""
    movie = Movie.find_by_imdb(materkey)
    if not movie:
        abort(404)
    return jsonify(**movie.extdata)


@main.route('/badmovie/<materkey>')
@logged_errors
def bad_movie(materkey):
    """Allow a refresh from the OMDB API if a movie looks incorrect."""
    use_rt = bool(int(request.args.get('use_rt', 0)))
    app_logger().info("Bad Movie GET - forcing %s with use_rt=%s", materkey, use_rt)
    movie = Movie.find_by_imdb(materkey, force=True, use_rt=use_rt)
    if not movie:
        app_logger().warn("No movie found for %s", materkey)
    return redirect(url_for('main.movie_display', moviekey=materkey))


@main.route('/person')
@main.route('/person/<name>')
@templated("person.html")
@use_error_page
def person_display(name=None):
    """Display 1 or all persons."""
    person, persons, person_name = None, None, ""

    if name:
        person = Attendee.find_by_index("index_name", name)
        if not person:
            raise ValueError('No attendee named %s could be found' % name)
        elif len(person) > 1:
            app_logger().warning("More than one person found for '%s'", name)

        person = person[0]  # find by index returns a list
        person_name = person.name.title()

        person.nights = [n for n in Night.find_all() if n.has_attendee(name)]
        person.nights.sort(key=attrgetter('datestr'), reverse=True)

        img_path = "static/people/%s.jpg" % person.name.lower()
        if not isfile(project_file(img_path)):
            img_path = "static/people/default.jpg"  # our default
        person.img = "/" + img_path
    else:
        # Don't fixup attendees for the list
        person_name = 'Listing Them All!'
        persons = Attendee.find_all()
        Attendee.sort(persons)

    return {
        'persons': persons,
        'person': person,
        'person_name': person_name
    }


@main.route('/night')
@main.route('/night/<datestr>', methods=['GET'])
@use_error_page
def night_display(datestr=None):
    """Movie night display - all, 1 , edit one, or save (on POST)."""
    if not datestr:
        # all nights
        nights = Night.find_all()
        nights.sort(key=attrgetter('datestr'))
        return template("night.html", movienights=nights, movie_night_name='ALL Movie Nights')

    # If we have a datestr but no mode, it's a detail display
    mode = request.args.get("mode", "").lower()
    if not mode and datestr.lower() != "add":
        # single night
        night = Night.find_datestr(datestr)
        Attendee.sort(night.attendees)
        return template(
            "night.html",
            movienight=night,
            movie_night_name=night.moviename if night else '???'
        )

    # Must be editing a night
    if datestr.lower() == "add" or mode == "add":
        # Adding
        night = Night(datestr="now", attendees=["Adam", "Marty"])
        mode = "add"
    else:
        # Editing
        night = Night.find_datestr(datestr)
        mode = "edit"
    return do_night_edit(night, mode)


@main.route('/night/<datestr>', methods=['POST'])
@require_login
@use_error_page
def night_save(datestr):
    """Save the night specified in the current request.

    On actual save without errors, redirect to display the night. Otherwise,
    re-display editing with errors
    """
    user = User.get_user()
    if not user or user.utype != "admin":
        raise NotAuthorized("You lack the requisite coolness to save a movie night")

    if not datestr:
        raise ValueError("WHOOPS! No movie night specified for save")

    mode = request.args.get("mode", "").lower()
    if not mode and datestr.lower() != "add":
        raise ValueError("Invalid movie night state for save: mode='%s',ds='%s'" % (mode, datestr))

    # They can change the datestr - the URL has the current datestr and the
    # form has the new datestr. Note that on add we'll default to "now"
    user_datestr = request.form.get('moviedate', '')

    if datestr.lower() == "add" or mode == "add":
        # Adding
        mode = "add"
        user_datestr = user_datestr or "now"  # Not in form? use current
        night = Night(datestr=user_datestr or "now")
    else:
        # Editing
        mode = "edit"
        user_datestr = user_datestr or datestr  # Not in form? use URL
        night = Night.find_datestr(datestr)     # We always search on URL
        if not night:
            raise ValueError("Attempt to edit non-existent movie night")
        if request.form.get('dodel', ''):
            # Delete requested
            app_logger().info("Delete requested for Night %s", datestr)
            night.delete()
            return redirect(url_for('main.main_page'))

    # Populate the "easy" fields
    night.datestr = user_datestr
    night.moviename = request.form.get('moviename', '')
    night.imdbid = request.form.get('movieimdbid', '')
    night.dinner = request.form.get('moviemeal', '')
    night.comments = request.form.get('moviecomments', '')

    # Handle attendees
    attendees = set([
        v.title()
        for k, v in request.form.items()
        if v and k.startswith('oldhat_')
    ])
    for a in request.form.get('newattendees', '').split(','):
        attendees.add(a.strip().title())
    attendees = attendees - set([""])
    night.attendees = list(sorted(attendees))

    Attendee.ensure_attendees(night.attendees)

    # Perform any validation we might need and then act
    errors = list(validate_night(night))
    if errors:
        # Oops!
        flash('.\n'.join(errors), category='error')
        return do_night_edit(night, mode)
    else:
        # Yippee!
        night.save()
        return redirect(url_for("main.night_display", datestr=night.datestr))


def validate_night(night):
    """Validate the night object and yield any errors we find."""
    if len(night.attendees) < 2:
        yield "Need at least 2 attendees"
    if not night.moviename:
        yield "Please enter *something* for the movie name"


def do_night_edit(night, mode):
    """Display the movie night edit screen."""
    attendees = Attendee.find_all()
    Attendee.sort(attendees)

    checked = set(night.attendees) | set(Attendee.OLIGARCHS)
    for att in attendees:
        att.checked = "checked" if att.name in checked else ""

    return template(
        "nightedit.html",
        movienight=night,
        mode=mode,
        attendees=attendees,
    )
