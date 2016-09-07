#!/usr/bin/env python

"""Nutbush Movie Night deployment hook."""

# pylama:ignore=E501,D103

import os
import os.path as pth
import subprocess
import logging
from flask import Flask, request, jsonify

# Create app and handle configuration
app = Flask(__name__)
app.config.from_pyfile('../default.config')
app.config.from_envvar('NBMN_CONFIG', silent=False)
app.secret_key = app.config.get('FLASK_SECRET', None)

# Handle debug flag from config file - and let them use anything truthy to
# our DEBUG flag
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger("deploy")

log.info('Application Deployment logging begin')

# They can specify that certain config variables are copied in to
# the system environment
for name in app.config.get("ENV_POPULATE"):
    val = str(app.config.get(name))
    log.info('Setting env[%s]=%s' % (name, val))
    os.environ[name] = val


def script_path(relpath):
    """Given path relative to this file, return absolute script file name."""
    base = pth.abspath(pth.dirname(__file__))
    return pth.join(base, relpath)


def run(*args):
    try:
        output = subprocess.check_output(args, stderr=subprocess.STDOUT)
        returncode = 0
        results = 'ok'
    except subprocess.CalledProcessError as e:
        output = e.output
        returncode = e.returncode
        results = 'error'
    try:
        output = output.decode('utf-8')
    except:
        output = "Could not decode output - forcing: " + str(output)
    return output, returncode, results


@app.route('/nbmnhook', methods=['GET'], strict_slashes=False)
def github_info():
    output, rc, results = run('git', 'log', '--max-count=1', '--color=never')
    return jsonify({
        'results': results,
        'output': output,
        'returncode': rc,
    })


@app.route('/nbmnhook', methods=['POST'], strict_slashes=False)
def github_push_hook():
    """Github is telling us what is up."""
    hook_type = request.headers.get('X-GitHub-Event', 'NO-HEADER-FOUND!!!')
    if hook_type != 'push':
        log.info("Only GitHub push events used, recvd %s" % hook_type)
        return jsonify({
            'results': 'ignored',
            'hook_type': hook_type,
        })

    push_data = request.get_json(force=True, cache=False) or dict()
    ref = push_data.get('ref', 'NO-REF-FOUND!!!')
    log.info("Got hook call with ref: %s" % ref)
    if ref != 'refs/heads/master':
        log.info('Deploy only activated for refs/heads/master')
        return jsonify({
            'results': 'ignored',
            'ref': ref,
        })

    super_name = app.config.get('DEPLOY_SUPER', None)
    if not super_name:
        log.info('Deploy not configured - DEPLOY_SUPER undefined')
        return jsonify({
            'results': 'error',
            'reason': 'No value found for  DEPLOY_SUPER'
        })

    output, returncode, results = run(script_path('./deploy'), super_name)
    return jsonify({
        'results': results,
        'output': output,
        'returncode': returncode,
    })


def main():
    """Entry point."""
    HOST = 'localhost'
    PORT = '10081'

    log.info("About to start serving deployment hook on %s:%d", HOST, PORT)
    from waitress import serve
    serve(app, host=HOST, port=PORT)

if __name__ == '__main__':
    main()
