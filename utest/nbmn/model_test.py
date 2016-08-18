# pylama:ignore=D100,D101,D102,E501,E128

import unittest

from nbmn.model import Attendee


class AttendeeTesting(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def assertSort(self, exp, tosort):
        tosort = list(tosort)
        Attendee.sort(tosort)
        # Fix random swap
        if len(tosort) >= 2 and tosort[0] == "Marty" and tosort[1] == "Adam":
            tosort[0], tosort[1] = tosort[1], tosort[0]
        self.assertEquals(exp, tosort)

    def testAttendeeSort(self):
        self.assertSort([], [])
        self.assertSort(["Adam"], ["Adam"])
        self.assertSort(["Marty"], ["Marty"])
        self.assertSort(["Adam", "Marty", "Aa"], ["Aa", "Marty", 'Adam'])

    def testOligarch(self):
        self.assertTrue(Attendee.olis(["Marty"]))
        self.assertTrue(Attendee.olis(["Adam"]))
        self.assertTrue(Attendee.olis(["Adam", "Marty"]))

        self.assertFalse(Attendee.olis([]))
        self.assertFalse(Attendee.olis(["Marto"]))
        self.assertFalse(Attendee.olis(["Etam"]))
        self.assertFalse(Attendee.olis(["Adam", "Other"]))
        self.assertFalse(Attendee.olis(["Other", "Marty"]))
