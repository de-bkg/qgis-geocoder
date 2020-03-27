import unittest
import os
import sys
from pprint import pprint

sys.path.append(os.path.split(os.path.dirname(os.path.abspath(__file__)))[0])

pprint(sys.exec_prefix)
pprint(sys.executable)
pprint(os.environ)

import test_bkg_geocoder
import test_init

if __name__ == "__main__":
    display = os.environ.get('DISPLAY')
    print('Display: {display}'.format(display=display))
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    # add tests to the test suite
    suite.addTests(loader.loadTestsFromModule(test_init))
    suite.addTests(loader.loadTestsFromModule(test_bkg_geocoder))
    runner = unittest.TextTestRunner(verbosity=3)
    result = runner.run(suite)