"""utils - a module providing utilities for the rest of nbnm."""

import sys
import traceback
import os.path as pth
from functools import wraps

from flask import abort, render_template, current_app

from .log import app_logger
from .model import User

# pylama:ignore=E501,D213


def project_file(relpath):
    """Given path relative to project root, return absolute file name."""
    # Kinda janky - we know this file is one directory up from the project
    # root, so we can work from there
    base = pth.abspath(pth.join(pth.dirname(__file__), '..'))
    return pth.join(base, relpath)


def template_context(**kwrds):
    """Create a template context.

    Includes the users specified keywords, logged in user information, and any
    configuration a template might need
    """
    usr = User.get_user()

    default = {
        'usr': usr
    }
    default.update(kwrds)
    return default


def template(template_name, **props):
    """Render the given template.

    The template context is from the given keyword arguments using
    template_context above. Note that flask will inject request, session,
    and g.  We inject usr.
    """
    return render_template(template_name, **template_context(**props))


def use_error_page(func):
    """Error handling decorator - must be inner-most annotation."""
    @wraps(func)
    def wrapper(*args, **kwrds):
        try:
            return func(*args, **kwrds)
        except:
            try:
                etype, evalue, etrace = sys.exc_info()
                app_logger().error("ERROR HANDLER => %s: %s\n%s\n", etype, evalue, etrace)
                errfmt = traceback.format_exception(etype, evalue, etrace)
                txtpre = "Unexpected error:"
                txtpost = '\n'.join(errfmt) if current_app.debug else evalue
                return template("error.html", errortext=txtpre+txtpost)
            except:
                app_logger().error("ERROR IN ERROR HANDLER - PUNTING - %s: %s\n%s\n" % sys.exc_info())
                return abort(500)  # Double Whoops!
    return wrapper


def logged_errors(func):
    """Error handling decorator - must be inner-most annotation."""
    @wraps(func)
    def wrapper(*args, **kwrds):
        try:
            return func(*args, **kwrds)
        except:
            etype, evalue, etrace = sys.exc_info()
            app_logger().error("ERROR HANDLER => %s: %s\n%s\n", etype, evalue, etrace)
            return abort(500)
    return wrapper


def templated(template_name):
    """Decorator taken from the Flasks docs.

    If a route function always renders the same template, then use the
    annotation and just return a dictionary instead
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ctx = f(*args, **kwargs)
            if ctx is None:
                ctx = {}
            elif not isinstance(ctx, dict):
                return ctx
            return template(template_name, **ctx)
        return decorated_function
    return decorator
