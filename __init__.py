# -*- coding: utf-8 -*-
'''
***************************************************************************
    __init__.py
    ---------------------
    Date                 : October 2018
    Author               : Christoph Franke
    Copyright            : (C) 2020 by Bundesamt für Kartographie und Geodäsie
    Email                : franke at ggr-planung dot de
***************************************************************************
*                                                                         *
*   This program is free software: you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 3 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************

initializes the plugin, making it known to QGIS.
'''

__author__ = 'Christoph Franke'
__date__ = '30/10/2018'
__copyright__ = 'Copyright 2020, Bundesamt für Kartographie und Geodäsie'

from qgis.gui import QgisInterface

from .bkg_geocoder_main import BKGGeocoderPlugin

def classFactory(iface: QgisInterface):
    '''
    load BKG geocoder plugin
    '''
    return BKGGeocoderPlugin(iface)
