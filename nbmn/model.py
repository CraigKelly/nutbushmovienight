"""model.py - Model classes for the app.

These classes are active-record(-ish) via the gludb library
"""

# pylama:ignore=D213

import random
from datetime import datetime

from gludb.simple import DBObject, Field, Index
from gludb.utils import parse_now_field
from flask import session, current_app

from .log import app_logger
from .imdb import norm_imdbid
from .remote import get_movie_data


@DBObject(table_name='Users')
class User(object):
    """System user.

    Simple class representing the current user - will be available
    in templates rendered with our function template as 'usr'.  Note that
    this is a LOGIN, not a movie night attendee which is a simple label
    bestowed by an oligarch
    """

    utype = Field('')
    name = Field('')
    email = Field('')
    photo = Field('')
    logins = Field(list)

    @Index
    def index_email(self):
        """Index users by email address."""
        return self.email

    @property
    def anon(self):
        """True if user is anonymous."""
        return not self.name

    @property
    def admin(self):
        """True if user is an admin."""
        return self.utype == "admin"

    @classmethod
    def set_user_session(cls, user_id=None):
        """Set the user in the current session."""
        if not user_id:
            user_id = ''
        session['user_id'] = user_id

    @classmethod
    def get_user(cls):
        """Return current user."""
        user_id = session.get('user_id', '')
        user = User.find_one(user_id) if user_id else None
        if user:
            # check for admin
            admins = current_app.config.get('ADMINS')
            if user.email in admins:
                user.utype = 'admin'
        else:
            # No user - just use a default
            user = User()
        return user


@DBObject(table_name="Movies")
class Movie(object):
    """Storage for a single movie."""

    name = Field('')
    imdbid = Field('')
    extdata = Field(dict)

    def setup(self, *args, **kwrds):
        """After construction we force imdbid to be correct."""
        self.imdbid = norm_imdbid(self.imdbid)

    @Index
    def index_imdbid(self):
        """Index by IMDB key."""
        return norm_imdbid(self.imdbid)

    @classmethod
    def find_by_imdb(cls, imdbid, force=False):
        """Find by IMDB id in DB - search remote sources if not found.

        If force is set to True, remote sources will be queries regardless of
        past data.
        """
        imdbid = norm_imdbid(imdbid)
        if not imdbid:
            raise ValueError('Missing IMDB ID - search is invalid')

        dbobj = cls.find_by_index('index_imdbid', imdbid)
        if not dbobj:
            # Whoops - not even in database
            dbobj = Movie(imdbid=imdbid)
        else:
            # We only want one object. In fact, if we're in force mode we'll
            # delete all the other movies
            if len(dbobj) > 1:
                app_logger().warning("Dup movies found for IMDB id %s", imdbid)
            if force:
                for xtra in dbobj[1:]:
                    app_logger().warning(
                        "Deleting dup movie imdbid:%s id:%s",
                        xtra.id, xtra.imdbid
                    )
                    xtra.delete()

            dbobj = dbobj[0]

        if force or not dbobj.extdata or not dbobj.extdata.get('omdb', None):
            # Check for override before asking for remote data
            extdata = MovieOverride.find_by_imdb(imdbid)
            if extdata:
                extdata = extdata.extdata
            else:
                extdata = get_movie_data(imdbid)

            dbobj.extdata = extdata
            ext_name = dbobj.extdata.get('omdb', {}).get('Title', '').strip()
            if ext_name:
                dbobj.name = ext_name
            dbobj.save()

        return dbobj


@DBObject(table_name="MovieOverrides")
class MovieOverride(Movie):
    """User-entered override for remote movie data.

    The override itself is handled in Movie.find_by_imdb.

    After saving a MovieOverride, you should be sure to use force=True in a
    call to Movie.find_by_imdb
    """

    @classmethod
    def find_by_imdb(cls, imdbid, force=False):
        """Find helper.

        Unlike our parent class, we are JUST a database lookup and WILL
        return if nothing is found.
        """
        imdbid = norm_imdbid(imdbid)
        if not imdbid:
            raise ValueError('Missing IMDB ID - search is invalid')

        dbobj = cls.find_by_index('index_imdbid', imdbid)
        if not dbobj:
            # Whoops - not even in database
            return None

        if len(dbobj) > 1:
            # We only want one object.
            app_logger().warning("Dup movies found for IMDB id %s", imdbid)
            for xtra in dbobj[1:]:
                app_logger().warning(
                    "Deleting dup movie imdbid:%s id:%s",
                    xtra.id, xtra.imdbid
                )
                xtra.delete()

        data = dbobj[0]
        return data


@DBObject(table_name="Attendees")
class Attendee(object):
    """We track attendees - who are not users."""

    OLIGARCHS = set(["Adam", "Marty"])

    @classmethod
    def olis(cls, lst):
        """Return true if all members of the iterable lst are oligarchs."""
        check = set(list(lst))
        if not check:
            return False
        if check - cls.OLIGARCHS:
            # Some left over - they must not be Oligarchs
            return False
        return True

    name = Field('')

    @property
    def urlname(self):
        """Name suitable for URL use."""
        return self.name

    @Index
    def index_name(self):
        """Index by name (duh)."""
        return self.name

    @classmethod
    def ensure_attendees(cls, required=None):
        """Ensure that all required attendees are in the DB."""
        existing = set([a.name for a in Attendee.find_all()])

        required = set(list(required)) if required else set()
        # Always require oligarchs
        for oli in cls.OLIGARCHS:
            required.add(oli)

        for name in required - existing:
            Attendee(name=name).save()

    @classmethod
    def sort(cls, attendees):
        """Sort attendees in place - we support both string and objects."""
        def sortkey(att):
            name = att if isinstance(att, str) else att.name
            prefix = '0' if name in cls.OLIGARCHS else '1'
            return prefix + name
        attendees.sort(key=sortkey)
        if len(attendees) >= 2 and cls.olis(attendees[:2]):
            if random.random() < 0.5:
                attendees[0], attendees[1] = attendees[1], attendees[0]


@DBObject("Nights")
class Night(object):
    """A single night at Nutbush Movie Night.

    Keyed by a string representation of the date in the format YYYYMMDD.
    """

    datestr = Field('')
    imdbid = Field('')
    moviename = Field('')
    dinner = Field('')
    comments = Field('')
    attendees = Field(list)
    ccsi = Field(0)

    DATE_FMT = "%Y%m%d"

    def setup(self, *args, **kwrds):
        """Insure fields are ok."""
        self.insure_data()

    def insure_data(self):
        """Provide a method to insure all the fields are correct."""
        self.datestr = self.str_from_date(self.datestr)
        self.imdbid = norm_imdbid(self.imdbid)
        try:
            if self.ccsi:
                self.ccsi = int(self.ccsi)
            else:
                self.ccsi = 0  # '', [], etc becomes 0
        except:
            pass  # Just allow non-int field for now

    @Index
    def index_datestr(self):
        """Index by datestr."""
        return self.datestr

    @Index
    def index_year(self):
        """Index by the year component of datestr."""
        return Night.date_from_str(self.datestr).year

    @classmethod
    def str_from_date(cls, date):
        """Insure the str or datetime is a str in the format we want."""
        if not date:
            return ""
        if isinstance(date, str):
            if date == "now":
                return datetime.now().strftime(Night.DATE_FMT)
            return date
        if isinstance(date, datetime):
            return date.strftime(Night.DATE_FMT)
        raise ValueError(
            "Could not convert date: unknown %s=>%s " % (type(date), str(date))
        )

    @classmethod
    def date_from_str(cls, date):
        """Insure the str or datetime is a datetime in the format we want."""
        if not date:
            return None
        if isinstance(date, str):
            if date == "now":
                return datetime.now()
            else:
                return datetime.strptime(date, Night.DATE_FMT)
        if isinstance(date, datetime):
            return date
        raise ValueError(
            "Could not convert date: unknown %s=>%s " % (type(date), str(date))
        )

    @classmethod
    def find_datestr(cls, date):
        """Helper for searching by date."""
        ds = Night.str_from_date(date)
        ns = cls.find_by_index('index_datestr', ds)
        if not ns:
            return None
        if len(ns) > 1:
            app_logger().warn("Found duplicate movie nights for date %s", ds)
        return ns[0]

    @property
    def listdate(self):
        """Displayable date - longer format."""
        return self.date_from_str(self.datestr).strftime("%A, %B %d, %Y")

    @property
    def listdate_short(self):
        """Displayable date - shorter format."""
        return self.date_from_str(self.datestr).strftime("%b %d, %Y")

    @property
    def listdate_js(self):
        """Displayable date that sorts correctly with JS-based date tables."""
        return self.date_from_str(self.datestr).strftime("%Y-%m-%d (%a, %b %d)")

    @property
    def listdate_ical(self):
        """Return version of a date compatible with iCalendar DTSTART."""
        return self.date_from_str(self.datestr).strftime("%Y%m%dT233000Z")

    @property
    def dstamp_ical(self):
        """Return string compatible with iCal DTSTAMP."""
        ndt = getattr(self, '_last_update', None) or getattr(self, '_create_date', None)
        if ndt:
            dt = parse_now_field(ndt)
        else:
            dt = datetime.now()
        return self.date_from_str(dt).strftime("%Y%m%dT%H%M%SZ")

    @property
    def comment_disp(self):
        """Displayable comment which includes HTML - BE CAREFUL.

        At one time this translated line breaks into break tags (`<br>`), but
        since we now use CKEditor for rich text input, we don't worry about it.
        """
        return str(self.comments)

    def has_attendee(self, a):
        """Return true if a in attendee list."""
        a = str(a).strip().lower()
        for chk in self.attendees:
            if a == chk.strip().lower():
                return True
        return False
