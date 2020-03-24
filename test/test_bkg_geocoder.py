# coding=utf-8
"""BKG Geocoding API test.

.. note:: This program is free software; you can redistribute it and/or modify
     it under the terms of the GNU General Public License as published by
     the Free Software Foundation; either version 2 of the License, or
     (at your option) any later version.

"""

__author__ = 'franke@ggr-planung.de'
__date__ = '2020-03-24'
__copyright__ = 'Copyright 2018, GGR'

import unittest
import sys
import os
from qgis.core import QgsVectorLayer
from unittest.mock import Mock, patch
import json

sys.path.append(os.path.split(os.path.dirname(os.path.abspath(__file__)))[0])
from geocoder.bkg_geocoder import BKGGeocoder
from geocoder.geocoder import Geocoding
from utilities import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()

# bkg key from environment variable (security reasons)
UUID = os.environ.get('BKG_UUID')


class MockedResponse:
    responses = {}
    def __init__(self, query):
        self.status_code = 200
        self.__query = query

    def json(self):
        return {'features': self.responses[self.__query]}

def mocked_get(*args, **kwargs):
    return MockedResponse(kwargs['params']['query'])


class BKGGeocodingTest(unittest.TestCase):
    """Test dialog works."""

    def setUp(self):
        """Runs before each test."""
        self.geocoder = BKGGeocoder(UUID)

    def tearDown(self):
        """Runs after each test."""
        pass

    @patch('requests.get', side_effect=mocked_get)
    def test_keys(self, mock_get):
        fn = 'A2-T1_adressen_mit-header_utf8.csv'
        fp = os.path.join(os.path.dirname(__file__), 'test_data', fn)
        f_mock = f'{fp}.results.json'
        with open(f_mock, 'r') as response_file:
            res = json.load(response_file)
            MockedResponse.responses = res

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
    suite = unittest.makeSuite(BKGGeocodingTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)


