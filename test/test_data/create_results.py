import csv
import sys
import os
from qgis.core import QgsVectorLayer
import json

FP = os.path.join(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(FP, '..'))
sys.path.append(os.path.join(FP, '..', '..'))
from geocoder.bkg_geocoder import BKGGeocoder
from geocoder.geocoder import Geocoding
from utilities import get_qgis_app

QGIS_APP, CANVAS, IFACE, PARENT = get_qgis_app()
UUID = os.environ.get('BKG_UUID')

FILES = {
    'A2-T1_adressen_mit-header_utf8.csv': {
        'Straße': 'strasse',
        'Hausnummer': 'haus',
        'Postleitzahl': 'plz',
        'Ort': 'ort',
    },
}


if __name__ == "__main__":

    geocoder = BKGGeocoder(UUID)
    for fn, fields in FILES.items():
        fp = os.path.join(os.path.dirname(__file__), fn)
        out_fp = f'{fp}.results.json'
        uri = f'file:/{fp}?delimiter=";"'
        layer = QgsVectorLayer(uri, "test", "delimitedtext")
        geocoding = Geocoding(layer, geocoder)
        res = {}
        for field_name, keyword in fields.items():
            geocoding.set_field(field_name, keyword=keyword, active=True)

        def feature_done(feature, results):
            res[geocoder.params['query']] = results

        geocoding.feature_done.connect(feature_done)
        geocoding.work()
        with open(out_fp, 'w') as res_file:
            json.dump(res, res_file)