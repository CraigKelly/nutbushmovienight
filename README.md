# Nutbush Movie Night

Originally hosted on GAE (Google App Engine), this is now a self-hosted
application.

See the git history for the "old" version and import_gae for the code used
to migrate the data.

Built with flask and should run behind a proxy like caddy or nginx.

## First things first

Make sure to `./setup` to bootstrap the virtualenv properly.

## Running

To demo on your local with no authentication, run `./run`

See configuration below, but you can get started with:

 * Copy `test/test.config` to `./current.config`
 * Change banner, debug, google props, amd rotten tomatoes API key
 * `./run`

You can also use the `tools` script instead: `./tools run`

## Configuration

To configure the application, copy `default.config` to a new file (location
and name can be anything), define the export environment variable
`NBMN_CONFIG` to point to the file, and then use the command `./run`.

Note that `run` will check for the env variable `NBMN_CONFIG`. If the
variable is missing, `run` will look for the file `current.config` (which has
been conveniently added to `.gitignore`) and automatically set `NBMN_CONFIG`
to the path of the file.

## Tools

The `tools` script can run the application, run unit tests, and has some other
tricks. Try `./tools help` for a list.

## Google Props

Go to the Google developer's console and set credentials for you app (which
you might need to create). The redirect URL should be `/oauthcallback` (the
default). Be sure to add localhost so that you can test on your local box
(e.g. http://localhost:8081/oauthcallback)

## Rotten Tomatoes

NBMN uses Rotten Tomatoes for movie information (but can fall back to
omdbapi.com if required). You'll need to get your own API key.
