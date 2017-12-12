"""main_app - the main functionality for Nutbush Movie Night."""

# pylama:ignore=E501,D213

from io import BytesIO
from os.path import isfile
from datetime import datetime
from operator import attrgetter

import requests

from flask import (
    abort,
    Blueprint,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    request,
    send_file,
    url_for
)

from .imdb import norm_imdbid
from .log import app_logger
from .auth import NotAuthorized, require_login
from .utils import logged_errors, template, templated, use_error_page, project_file
from .model import User, Movie, Night, Attendee, MovieOverride
from .remote import create_omdb_poster_get
from .slack import notify

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
    nights = nights[:MAX_NIGHTS]

    for night in nights:
        night.thumb = url_for('main.movie_image', imdbkey=night.imdbid)

    return {
        'movienights': nights
    }


@main.route('/debuglogin')
@require_login
@use_error_page
def debug_login():
    """Just a simple page to trigger a login, which is handy for the DEBUG_LOGIN env var."""
    return main_page()


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
        movie.poster = url_for('main.movie_image', imdbkey=movie.imdbid)
        return movie

    if moviekey:
        movie = fixup(Movie.find_by_imdb(moviekey))
        return {'movie': movie, 'movie_name': movie.name or '???'}
    else:
        movies = [fixup(m) for m in Movie.find_all()]
        movies.sort(key=attrgetter('name'))
        return {'movies': movies, 'movie_name': 'ALL'}


@main.route('/moviedata/<imdbkey>')
@logged_errors
def movie_data(imdbkey):
    """Movie lookup via remote API."""
    movie = Movie.find_by_imdb(imdbkey)
    if not movie:
        abort(404)
    movie.extdata['Poster'] = url_for('main.movie_image', imdbkey=movie.imdbid)
    return jsonify(**movie.extdata)


@main.route('/movieimage/<imdbkey>')
@logged_errors
def movie_image(imdbkey):
    """Movie image retrieval via remote API."""
    movie = Movie.find_by_imdb(imdbkey)
    if not movie:
        abort(404)

    local_path = project_file('static/posters/%s.jpg' % movie.imdbid)
    if isfile(local_path):
        buffer_image = open(local_path, "rb")
        mimetype = 'image/jpeg'
        imgsrc = 'Local Disk (%s)' % local_path
    else:
        r = create_omdb_poster_get(imdbkey)
        if r.status_code == 200:
            buffer_image = BytesIO(r.content)
            buffer_image.seek(0)
            mimetype = r.headers['Content-Type']
            imgsrc = 'OMDB Poster API'
        else:
            app_logger().warn('Poster API %s found nothing (%s)', movie.imdbid, str(r.status_code))
            poster = movie.extdata.get('omdb', {}).get('Poster', '')
            r = None
            if poster:
                r = requests.get(poster)

            if r and r.status_code == 200:
                buffer_image = BytesIO(r.content)
                buffer_image.seek(0)
                mimetype = r.headers['Content-Type']
                imgsrc = 'OMDB Post Link in Data'
            else:
                app_logger().warn('No Poster Link in data for %s', movie.imdbid)
                local_path = project_file('static/default_movie_thumb.png')
                buffer_image = open(local_path, 'rb')
                mimetype = 'image/png'
                imgsrc = 'Default Poster (%s)' % local_path

    app_logger().info('Send image for %s from %s', movie.imdbid, imgsrc)

    return send_file(buffer_image, mimetype=mimetype)


@main.route('/badmovie/<imdbkey>')
@logged_errors
def bad_movie(imdbkey):
    """Allow a refresh from the OMDB API if a movie looks incorrect."""
    app_logger().info("Bad Movie GET - forcing %s", imdbkey)
    movie = Movie.find_by_imdb(imdbkey, force=True)
    if not movie:
        app_logger().warn("No movie found for %s", imdbkey)
    return redirect(url_for('main.movie_display', moviekey=imdbkey))


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

        for p in persons:
            p.nights = []
        for n in Night.find_all():
            for p in persons:
                if n.has_attendee(p.name):
                    p.nights.append(n)

        for p in persons:
            p.nights.sort(key=attrgetter('datestr'), reverse=True)
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
            notify("%s just deleted %s", g.user.email, datestr)
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
    night.insure_data()
    errors = list(validate_night(night))
    if errors:
        # Oops!
        flash('.\n'.join(errors), category='error')
        return do_night_edit(night, mode)
    else:
        # Yippee!
        night.save()
        night_url = url_for("main.night_display", datestr=night.datestr)
        notify(
            "%s just saved data for movie night: %s\nSee it here: <%s%s>",
            g.user.email,
            night.listdate,
            current_app.config.get("SLACK_URL_BASE", ""),
            night_url
        )
        return redirect(night_url)


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

    if mode == "add":
        cancel_url = url_for("main.main_page")
    else:
        cancel_url = url_for("main.night_display", datestr=night.datestr)

    return template(
        "nightedit.html",
        movienight=night,
        mode=mode,
        attendees=attendees,
        cancel_url=cancel_url
    )


def _default_override(imdbid):
    FIELDS = [
        'Actors', 'Awards', 'BoxOffice', 'Country', 'DVD', 'Director', 'Genre',
        'Language', 'Metascore', 'Plot', 'Poster', 'Production', 'Rated',
        'Released', 'Runtime', 'Title', 'Type', 'Website', 'Writer', 'Year',

        'imdbRating', 'imdbVotes',

        'tomatoConsensus', 'tomatoFresh', 'tomatoImage', 'tomatoMeter',
        'tomatoRating', 'tomatoReviews', 'tomatoRotten', 'tomatoURL',
        'tomatoUserMeter', 'tomatoUserRating', 'tomatoUserReviews',
    ]
    d = {
        'imdbID': imdbid,
        'Response': True
    }
    for f in FIELDS:
        d[f] = ''
    return d


@main.route('/override/<imdbid>', methods=['GET'])
@require_login
@use_error_page
def movie_override(imdbid):
    """Show the movie override form."""
    user = User.get_user()
    if not user or user.utype != "admin":
        raise NotAuthorized("You lack the requisite coolness to override movies")

    imdbid = norm_imdbid(imdbid)

    over = MovieOverride.find_by_imdb(imdbid)
    if over:
        previous = True
        over = over.extdata.get("omdb", None)
        if not over:
            over = _default_override(imdbid)
    else:
        previous = False
        over = _default_override(imdbid)

    return template(
        "movieoverride.html",
        over=over,
        previous=previous,
    )


@main.route('/override/<imdbid>', methods=['POST'])
@require_login
@use_error_page
def movie_override_save(imdbid):
    """Save the movie override."""
    user = User.get_user()
    if not user or user.utype != "admin":
        raise NotAuthorized("You lack the requisite coolness to save a movie override")

    movie_over = MovieOverride.find_by_imdb(imdbid)
    if not movie_over:
        movie_over = MovieOverride(imdbid=imdbid)

    FIELDS = [
        'Actors', 'Awards', 'BoxOffice', 'Country', 'DVD', 'Director', 'Genre',
        'Language', 'Metascore', 'Plot', 'Poster', 'Production', 'Rated',
        'Released', 'Runtime', 'Title', 'Type', 'Website', 'Writer', 'Year',
    ]
    over = _default_override(imdbid)
    for fld in FIELDS:
        over[fld] = request.form.get(fld, '')

    movie_over.extdata = {
        "omdb": over,
        "update_time": str(datetime.now())
    }
    movie_over.name = over.get('Title', 'UNTITLED')
    movie_over.save()
    Movie.find_by_imdb(movie_over.imdbid, force=True)

    return redirect(url_for('main.movie_display', moviekey=movie_over.imdbid))


@main.route('/override-delete/<imdbid>', methods=['POST'])
@require_login
@use_error_page
def movie_override_delete(imdbid):
    """Delete the movie override."""
    user = User.get_user()
    if not user or user.utype != "admin":
        raise NotAuthorized("You lack the requisite coolness to delete a movie override")

    movie_over = MovieOverride.find_by_imdb(imdbid)
    if movie_over:
        movie_over.delete()

    Movie.find_by_imdb(movie_over.imdbid, force=True)
    return redirect(url_for('main.movie_display', moviekey=movie_over.imdbid))
