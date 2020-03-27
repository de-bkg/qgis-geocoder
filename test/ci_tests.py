import unittest
import os
import sys

sys.path.append(os.path.split(os.path.dirname(os.path.abspath(__file__)))[0])

import test_bkg_geocoder
import test_init

if __name__ == "__main__":
    print(f'Display: {os.environ["DISPLAY"]}')
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    # add tests to the test suite
    suite.addTests(loader.loadTestsFromModule(test_init))
    suite.addTests(loader.loadTestsFromModule(test_bkg_geocoder))
    runner = unittest.TextTestRunner(verbosity=3)
    result = runner.run(suite)