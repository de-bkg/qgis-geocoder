# coding=utf-8
"""BKG Geocoding API test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'franke@ggr-planung.de'
__date__ = '2018-10-19'
__copyright__ = 'Copyright 2018, GGR'

import unittest
import csv
import re

from ..geocode import BKGGeocoder


UUID = "" # Key, welcher vom BKG ausgegeben wird
URL = "http://sg.geodatenzentrum.de/gdz_geokodierung__{key}/geosearch".format(key=UUID)


class BKGAPITest(unittest.TestCase):
    """Test dialog works."""

    def setUp(self):
        """Runs before each test."""
        self.geocoder = BKGGeocoder(URL)

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_special_kw(self):
        kwargs = {
            'plz_ort': '91541 Rothenburg ob der Tauber',
            'strasse': 'Spitalgasse',
            'haus': 43
        }
        self.geocoder.query(**kwargs)
        kwargs = {
            'ort': 'Berlin',
            'strasse_hnr': 'Straße des 17.Juni 134-135'
        }
        self.geocoder.query(**kwargs)

    def test_keys(self):
        with open('test.csv', newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=';')
            header = next(reader, None)
            for row in reader:
                kwargs = {}
                for i, h in enumerate(header):
                    kwargs[h] = row[i]
                results = self.geocoder.query(**kwargs)

    def test_wo_keys(self):
        with open('test2.csv', newline='') as csvfile:
            reader = csv.reader(csvfile, delimiter=';')
            header = next(reader, None)
            for row in reader:
                args = []
                for a in row:
                    split = re.findall(r"[\w'\-]+", a)
                    args.extend(split)
                results = self.geocoder.query(*args)


if __name__ == "__main__":
    suite = unittest.makeSuite(BKGAPITest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)


