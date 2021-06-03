"""Authentication Flask Blueprint for login functionality in our app."""

import os
import sys
import traceback

from functools import partial, wraps

from flask import redirect, request, flash, abort, g, url_for
from flask.globals import LocalProxy, _lookup_app_object

try:
    from flask import _app_ctx_stack as stack
except ImportError:
    from flask import _request_ctx_stack as stack

from flask_dance.consumer import (
    OAuth2Session,
    OAuth2ConsumerBlueprint,
    oauth_authorized,
    oauth_error
)
from flask_dance.utils import invalidate_cached_property
from urlobject import URLObject

from gludb.utils import now_field

from .log import app_logger
from .model import User


class NotAuthorized(Exception):
    """Simple helper exception for unauthorized users."""

    def __init__(self, msg):
        """Init the exception and write a log entry for later checking."""
        super(NotAuthorized, self).__init__(msg)
        try:
            app_logger().warning("Unauthorized access: %s" % msg)
        except:
            pass  # No exceptions when creating an exception!


def require_login(func):
    """Simple decorator helper for requiring login.

    Used on functions decorated with flask route: make sure that it's LAST
    in the decorator list so that the flask magic happens.

    Important: we are assuming the blueprint endpoint auth.login exists
    """
    @wraps(func)
    def wrapper(*args, **kwrds):
        try:
            # DEBUG login set in env
            debug_email = os.environ.get('DEBUG_EMAIL', '')
            if debug_email:
                # we have a manual user login
                users = User.find_by_index('index_email', debug_email)
                if users:
                    user = users[0]  # Always first found
                else:
                    user = User(email=debug_email)
                user.name = ' '.join(debug_email.split('@')[0].split('.')).title()
                user.photo = '/static/anonymous_person.png'
                user.utype = 'admin'
                user.logins.append(now_field())
                user.save()
                User.set_user_session(user.id)
                app_logger().warn("Logged in DEBUG user id %s, email %s" % (user.id, user.email))
                flash("You are logged in as " + user.name, category='info')
                setattr(g, 'user', user)
                return func(*args, **kwrds)

            # Normal login
            user = User.get_user()
            if user:
                setattr(g, 'user', user)
                return func(*args, **kwrds)
            else:
                # Proceed with auto login as per usual
                url = url_for('auth.login', redir=request.url)
                return redirect(url)
        except:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            log = app_logger()
            log.warning("Unexpected error: %s", exc_value)
            log.error(''.join(traceback.format_exception(
                exc_type, exc_value, exc_traceback
            )))
            return abort(500)

    return wrapper


class CustomOAuth2Session(OAuth2Session):
    """This hacky class is here because for whatever reason the Proxy fix for
    Flask isn't working with flask_dance. Ugh, should have just written my own
    to start.
    """
    def __init__(self, blueprint=None, base_url=None, *args, **kwargs):
        self._redirect_uri = kwargs.get('redirect_uri', None)
        super().__init__(*args, **kwargs)
        self.blueprint = blueprint
        self.base_url = URLObject(base_url)
        invalidate_cached_property(self, "token")

    @property
    def redirect_uri(self):
        return self._redirect_uri

    @redirect_uri.setter
    def redirect_uri(self, url):
        new_uri = (url or '')
        if not ('localhost' in new_uri or '127.0.0' in new_uri):
            new_uri = new_uri.replace("http:", "https:")
        if new_uri != self._redirect_uri:
            app_logger().debug("ouath2 redirect_uri changing from %s to %s", new_uri, self._redirect_uri)
        self._redirect_uri = new_uri


# Make the google blueprint (taken from their contrib code)
auth = OAuth2ConsumerBlueprint(
    "auth",
    __name__,
    client_id=None,  # Handled via app config
    client_secret=None,  # Handled via app config
    scope=["profile", "email"],
    base_url="https://www.googleapis.com/",
    authorization_url="https://accounts.google.com/o/oauth2/auth",
    token_url="https://accounts.google.com/o/oauth2/token",
    redirect_url=None,
    redirect_to=None,
    login_url=None,
    authorized_url=None,
    authorization_url_params={},
    session_class=CustomOAuth2Session,
)

auth.from_config["client_id"] = "GOOGLE_CLIENT_ID"
auth.from_config["client_secret"] = "GOOGLE_CLIENT_SECRET"


@auth.before_app_request
def set_applocal_session():
    """Make sure we can see the google oauth in the session."""
    ctx = stack.top
    ctx.google_oauth = auth.session

google_api = LocalProxy(partial(_lookup_app_object, "google_oauth"))


def login_fail(msg):
    """Show and log login failure."""
    flash(msg, category="error")
    app_logger().error(msg)
    return False


@oauth_authorized.connect
def log_in_event(blueprint, token):
    """create/login local user on successful OAuth login."""
    User.set_user_session()  # Clear previous session

    if not token:
        return login_fail("Failed to log in")

    resp = blueprint.session.get("/oauth2/v1/userinfo")
    if not resp.ok:
        return login_fail("Failed to login user!")

    data = resp.json()

    email = data.get('email', '')
    if not email:
        return login_fail("Google failed to supply an email address")

    users = User.find_by_index('index_email', email)
    if users:
        user = users[0]  # Always first found
    else:
        user = User(email=email)

    # Update the user info and save the session info
    user.name = data.get('name', email)
    user.photo = data.get('picture', '/static/anonymous_person.png')
    user.logins.append(now_field())
    user.save()

    User.set_user_session(user.id)
    app_logger().info("Logged in user id %s, email %s" % (user.id, user.email))
    flash("You are logged in as " + user.name, category='info')


# notify on OAuth provider error
@oauth_error.connect
def google_error(blueprint, error, error_description=None, error_uri=None):
    """Handle any errors seen by flask-dance."""
    login_fail("OAuth login failure: [%s] %s (uri=%s)" % (
        error, error_description, error_uri
    ))


@auth.route('/logout')
def logout():
    """Logout the current user."""
    User.set_user_session()
    redir_url = request.args.get("redir", None)
    if not redir_url:
        redir_url = '/'
    flash('You are logged out', category='info')
    return redirect(redir_url)
