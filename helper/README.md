# NBMN Helpers

Currently this directory contains a few small scripts for handling a redeploy
via a GitHub webhook. Note that it requires current.config support, that you
are running nbmn with supervisord, and then the user it is running under has
the correct permissions to run `supervisorctl` (for details on getting started
with the latter see https://coffeeonthekeyboard.com/using-supervisorctl-with-linux-permissions-but-without-root-or-sudo-977/)
