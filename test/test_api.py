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
import sys
import os
from qgis.core import QgsVectorLayer

sys.path.append(os.path.split(os.path.dirname(os.path.abspath(__file__)))[0])
from geocoder.bkg_geocoder import BKGGeocoder
from geocoder.geocoder import Geocoding
from utilities import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()

# bkg key from environment variable (security reasons)
UUID = os.environ.get('BKG_UUID')


class BKGAPITest(unittest.TestCase):
    """Test dialog works."""

    def setUp(self):
        """Runs before each test."""
        self.geocoder = BKGGeocoder(UUID)

    def tearDown(self):
        """Runs after each test."""
        pass

    def test_keys(self):
        fn = os.path.join('A2-T1_adressen_mit-header_utf8.csv')
        fp = os.path.join(os.path.dirname(__file__), 'test_data', fn)
        uri = f'file:/{fp}?delimiter=";"'
        vlayer = QgsVectorLayer(uri, "test", "delimitedtext")
        geocoding = Geocoding(vlayer, self.geocoder)
        geocoding.set_field('Straße', keyword='strasse', active=True)
        geocoding.set_field('Hausnummer', keyword='haus', active=True)
        geocoding.set_field('Postleitzahl', keyword='plz', active=True)
        geocoding.set_field('Ort', keyword='ort', active=True)

        # not threaded
        geocoding.work()


if __name__ == "__main__":
    suite = unittest.makeSuite(BKGAPITest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)


