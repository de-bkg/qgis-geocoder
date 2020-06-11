# coding=utf-8
"""
BKG Geocoding API test.
"""

__author__ = 'Christoph Franke'
__date__ = '2020-03-24'

import unittest
import sys
import os
from qgis.core import QgsVectorLayer, QgsPoint
from unittest.mock import patch
import json

sys.path.append(os.path.split(os.path.dirname(os.path.abspath(__file__)))[0])
from geocoder.bkg_geocoder import BKGGeocoder
from geocoder.geocoder import Geocoding, FieldMap, ReverseGeocoding
from utilities import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()

# bkg key from environment variable (security reasons)
UUID = os.environ.get('BKG_UUID')


class MockedResponse:
    responses = {}
    def __init__(self, query, status_code=200):
        self.status_code = status_code
        self.__query = query

    def json(self):
        return {'features': self.responses[self.__query]}

def mocked_geocode_get(*args, **kwargs):
    return MockedResponse(kwargs['params']['query'])

def mocked_reverse_get(*args, **kwargs):
    params = kwargs['params']
    pnt = QgsPoint(params['lon'], params['lat'])
    return MockedResponse(pnt.asWkt())


class BKGGeocodingTest(unittest.TestCase):
    """Test dialog works."""

    def setUp(self):
        """Runs before each test."""
        self.geocoder = BKGGeocoder(UUID)

    def tearDown(self):
        """Runs after each test."""
        pass

    @patch('requests.get', side_effect=mocked_geocode_get)
    def test_geocoding(self, mock_get):
        fn = 'A2-T1_adressen_mit-header_utf8.csv'
        fp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'test_data', fn)
        f_mock = f'{fp}.results.json'
        with open(f_mock, 'r') as response_file:
            res = json.load(response_file)
            MockedResponse.responses = res

        prefix = 'file:/'
        if os.name != 'nt':
            prefix += '/'
        uri = f'{prefix}{fp}?delimiter=";"'
        layer = QgsVectorLayer(uri, "test", "delimitedtext")
        assert layer.isValid(), "Input layer is not valid"
        field_map = FieldMap(layer)
        field_map.set_field('Straße', keyword='strasse', active=True)
        field_map.set_field('Hausnummer', keyword='haus', active=True)
        field_map.set_field('Postleitzahl', keyword='plz', active=True)
        field_map.set_field('Ort', keyword='ort', active=True)
        geocoding = Geocoding(self.geocoder, field_map)
        # not threaded
        geocoding.work()

    @patch('requests.get', side_effect=mocked_reverse_get)
    def test_reverse(self, mock_get):
        fn = 'mit_koordinaten.csv'
        fp = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          'test_data', fn)
        f_mock = f'{fp}.results.json'
        with open(f_mock, 'r') as response_file:
            res = json.load(response_file)
            MockedResponse.responses = res

        uri = f'file:/{fp}?crs=epsg:25832&xField=x&yField=y&delimiter=";"'
        layer = QgsVectorLayer(uri, "test", "delimitedtext")
        geocoding = ReverseGeocoding(self.geocoder, layer.getFeatures())
        # not threaded
        geocoding.work()

if __name__ == "__main__":
    suite = unittest.makeSuite(BKGGeocodingTest)
    runner = unittest.TextTestRunner(verbosity=2)
    runner.run(suite)


