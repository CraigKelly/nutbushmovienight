# pylama:ignore=D100,D101,D102,E501,E128

import unittest

from nbmn.remote import _parse_url, norm_imdbid


class RemoteHelperTesting(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def assertUrl(self, url, exp_bare, exp_qs):
        bare, qs = _parse_url(url)
        self.assertEqual(exp_bare, bare)
        self.assertEqual(exp_qs, qs)

    def testParseUrl(self):
        self.assertUrl(None, None, None)
        self.assertUrl("", None, None)

        self.assertUrl("http://a.b.com", "http://a.b.com", dict())
        self.assertUrl("http://a.b.com/d1/d2/a.html", "http://a.b.com/d1/d2/a.html", dict())

        self.assertUrl("http://a.b.com?a=b&x=y",
            "http://a.b.com",
            {'a': 'b', 'x': 'y'}
        )
        self.assertUrl("http://a.b.com/d1/d2/a.html?a=b&x=y",
            "http://a.b.com/d1/d2/a.html",
            {'a': 'b', 'x': 'y'}
        )

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
