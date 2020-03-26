import unittest
import os
import sys

sys.path.append(os.path.split(os.path.dirname(os.path.abspath(__file__)))[0])
if __name__ == "__main__":
    from test import test_bkg_geocoder, test_init, qgis_interface
else:
    from ..test import test_bkg_geocoder, test_init, qgis_interface

def run_all():

    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    # add tests to the test suite
    suite.addTests(loader.loadTestsFromModule(test_init))
    suite.addTests(loader.loadTestsFromModule(test_bkg_geocoder))
    runner = unittest.TextTestRunner(verbosity=3)
    result = runner.run(suite)

if __name__ == "__main__":
    run_all()