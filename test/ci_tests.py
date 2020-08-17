import unittest

import test_init
import test_bkg_geocoder

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    # add tests to the test suite
    suite.addTests(loader.loadTestsFromModule(test_init))
    suite.addTests(loader.loadTestsFromModule(test_bkg_geocoder))
    runner = unittest.TextTestRunner(verbosity=3)
    result = runner.run(suite)