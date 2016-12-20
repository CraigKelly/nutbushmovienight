# pylama:ignore=D100,D101,D102,E501,E128

import unittest

from nbmn.imdb import norm_imdbid


class RemoteHelperTesting(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testNormImdb(self):
        self.assertEqual('', norm_imdbid(0))
        self.assertEqual('', norm_imdbid('0'))
        self.assertEqual('', norm_imdbid(None))
        self.assertEqual('', norm_imdbid([]))
        self.assertEqual('', norm_imdbid(''))

        self.assertEqual('tt0000001', norm_imdbid(1))
        self.assertEqual('tt0000001', norm_imdbid('1'))
        self.assertEqual('tt0000001', norm_imdbid('0000000001'))
        self.assertEqual('tt0000001', norm_imdbid('tt1'))
        self.assertEqual('tt0000001', norm_imdbid('tt0000000001'))
        self.assertEqual('tt0000001', norm_imdbid('tt0000001'))

        self.assertEqual('tt1234567', norm_imdbid(1234567))
        self.assertEqual('tt1234567', norm_imdbid('1234567'))
        self.assertEqual('tt1234567', norm_imdbid('tt1234567'))
