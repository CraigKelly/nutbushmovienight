"""lawyer - lawyer-ese, boilerplate, and simple text."""

# pylama:ignore=E501

from flask import Blueprint, request, send_from_directory

from .utils import templated, use_error_page


lawyer = Blueprint('lawyer', __name__)


# The easiest part - we have some templates that don't need any work before
# being displayed
def make_vanilla_template(route, template_name):
    """Content-only page helper.

    If we just render a template and don't add any extra context parameters
    we can just do a vanilla url route. Note that we name it by replacing '/'
    with '_' so if the rule is for '/foo/bar', then the call to get the url
    would be url_for('main.foo_bar')
    """
    @templated(template_name)
    @use_error_page
    def f():
        return {}
    lawyer.add_url_rule(route, route.replace('/', '_').lstrip('_'), f)

make_vanilla_template("/about",   "about.html")
make_vanilla_template("/faq",     "faq.html")
make_vanilla_template("/tos",     "tos.html")
make_vanilla_template("/cwm",     "cwm.html")
make_vanilla_template("/a50",     "a50.html")


# Some static routes for files that a nice website should provide
@lawyer.route('/robots.txt')
@lawyer.route('/humans.txt')
def static_text_files():
    """Map certain files in our static folder."""
    return send_from_directory("static/", request.path[1:])
