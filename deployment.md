# New Deployment Plan

Currently, we assume a working dir already set up with pyenv/pipenv to match our
Pipfile. Lots of this manual work needs to be replaced with a better run script...

To set up a new server, we need to build a decently recent Python 3.6 (note that
once this is happening, we'll remove the detailed Python dep in the Pipfile).
Note that we also assume the presence of a script named `dev-up` that prepares
the workstation for Python builds.

```
$ dev-up
$ wget Python-3.6.awesome.tgz
$ tar -zxf Python-3.6.awesome.tgz
$ cd Python-3.6.awesome.tgz
$ ./configure --prefix=/opt/py --enable-optimizations
$ sudo make install
```

We are assuming that we already have a `www-data` user. However, we want a special
home directory for this app and that user:

```
$ cd /opt
$ sudo mkdir www-data-home
$ sudo chown www-data:www-data www-data-home/
```

At this point, we should be able to run a script that insures the latest Pipfile
deps and then uses `./run`:

```
#!/bin/bash

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

set -a

SHELL=/bin/bash
LANG=en_US.UTF-8
HOME=/opt/www-data-home
PATH=/opt/py/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin

set +a

pipenv install --deploy

cd "${SCRIPT_DIR}"
AUTO_CFG="${SCRIPT_DIR}/current.config"

if [ "" == "$NBMN_CONFIG" ]; then
    if [ -f "$AUTO_CFG" ]; then
        echo "NBNM_CONFIG not defined, but found auto config file name"
        echo "Setting to $AUTO_CFG"
        export NBMN_CONFIG="$AUTO_CFG"
    else
        echo "NOTE! NBMN_CONFIG is not defined and NO auto .config"
        echo " ... ($AUTO_CFG) was NOT found ...."
        echo "Only the default values in $SCRIPT_DIR/default.config"
        echo "will be used by nbnm"
    fi
fi

python "$SCRIPT_DIR/main.py"
```
