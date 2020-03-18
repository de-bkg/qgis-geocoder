import csv
import sys
import os
from qgis.core import QgsVectorLayer

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
        out_fp = f'{os.path.splitext(fp)[0]}_results.csv'
        uri = f'file:/{fp}?delimiter=";"'
        layer = QgsVectorLayer(uri, "test", "delimitedtext")
        geocoding = Geocoding(layer, geocoder)
        for field_name, keyword in fields.items():
            geocoding.set_field(field_name, keyword=keyword, active=True)
        with open(out_fp, 'w', newline='', encoding='utf-8') as outcsv:
            global writer
            writer = None

            def feature_done(feature, results):
                global writer
                if not results:
                    return
                fid = feature.attribute(0)
                for result in results:
                    x, y = result['geometry']['coordinates']
                    properties = result['properties']
                    if not writer:
                        fieldnames = ['ID', 'x', 'y'] + list(properties.keys())
                        writer = csv.DictWriter(outcsv, fieldnames=fieldnames,
                                                delimiter=';')
                        writer.writeheader()
                    properties['ID'] = fid
                    properties['x'] = x
                    properties['y'] = y
                    writer.writerow(properties)

            geocoding.feature_done.connect(feature_done)
            geocoding.work()
