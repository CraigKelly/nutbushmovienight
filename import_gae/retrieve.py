#!/usr/bin/env python3

"""Download all data available from our GAE app."""

# Note: requires python wget (pip install wget)

import os

import wget

URL = 'http://nutbushmovienight.appspot.com/gimme'
OUT = 'gimme.json'
DISP_BAR = wget.bar_thermometer


def previous_check():
    """If we had a previous run, move it to backup status."""
    if os.path.isfile(OUT):
        backup = OUT + '.backup'
        print('Found previous %s - moving to %s' % (OUT, backup))
        if os.path.isfile(backup):
            print('IMPORTANT: removed previous %s' % backup)
            os.remove(backup)
        os.rename(OUT, backup)


def main():
    """Download our data from GAE."""
    print('IMPORTANT!!! GAE **will** mess with the cache - check the file')
    print('you receive for correctness!!!')
    print('*IN FACT* you should probably manually flush the cache in the')
    print('appspot app before running this script')
    print('')
    print(('GETTING %s' % URL))
    print(('File will be named %s' % OUT))
    previous_check()
    filename = wget.download(URL, out=OUT, bar=DISP_BAR)
    print('')
    print(('Downloaded %s' % filename))

if __name__ == "__main__":
    main()
