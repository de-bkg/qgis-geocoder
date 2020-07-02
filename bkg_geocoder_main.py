# -*- coding: utf-8 -*-
'''
***************************************************************************
    bkg_geocoder_main.py
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

main entry point of the plugin, manages the main widget
'''

__author__ = 'Christoph Franke'
__date__ = '30/10/2018'
__copyright__ = 'Copyright 2020, Bundesamt für Kartographie und Geodäsie'

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsMapLayer, QgsVectorLayer
from qgis.gui import QgisInterface

# init resources
from .resources import *
from .interface.main_widget import MainWidget


class BKGGeocoderPlugin:
    '''
    Geocoder plugin to use with BKG geocoding API
    '''

    def __init__(self, iface: QgisInterface):
        '''
        Parameters
        ----------
        iface : QgisInterface
            interface to the QGIS UI
        '''

        self.iface = iface
        self.actions = []
        self.menu = '&BKG Geocoder'
        self.toolbar = self.iface.addToolBar(u'BKGGeocoder')
        self.toolbar.setObjectName(u'BKGGeocoder')

        self.canvas = self.iface.mapCanvas()

        self.pluginIsActive = False
        self.mainwidget = None

    def initGui(self):
        '''
        override, add entry points (actions) for the plugin
        '''
        # toolbar icon
        icon_path = ':/plugins/bkg_geocoder/icon.png'
        icon = QIcon(icon_path)
        action = QAction(icon, 'BKG Geocoder', self.iface.mainWindow())
        action.triggered.connect(lambda: self.run())
        self.toolbar.addAction(action)
        self.iface.addPluginToVectorMenu('Geokodierung', action)

        # open dialog on right click feature in legend
        self.legend_action = QAction(icon,
                                     'BKG Geocoder: Layer geokodieren',
                                     self.iface)
        self.legend_action.triggered.connect(
            lambda: self.run(
                layer=self.iface.layerTreeView().currentLayer()
            )
        )

        self.iface.addCustomActionForLayerType(
            self.legend_action, "", QgsMapLayer.VectorLayer, True)

    def onClosePlugin(self):
        '''
        override, close UI on closing plugin
        '''

        # disconnects
        self.mainwidget.closingWidget.disconnect(self.onClosePlugin)
        self.mainwidget.close()

        self.pluginIsActive = False

    def unload(self):
        '''
        remove the plugin and its UI from the QGIS interface
        '''
        for action in self.actions:
            self.iface.removePluginMenu('&BKG Geocoder', action)
            self.iface.removeToolBarIcon(action)
        self.iface.removeCustomActionForLayerType(self.legend_action)
        self.iface.actionPan().trigger()
        # remove the toolbar
        if self.toolbar:
            del self.toolbar
        # remove widget
        if self.mainwidget:
            self.mainwidget.close()
            self.mainwidget.unload()
            self.mainwidget.deleteLater()
            self.mainwidget = None
        self.pluginIsActive = False

    def run(self, layer: QgsVectorLayer = None):
        '''
        open the plugin

        Parameters
        ----------
        layer : QgsVectorLayer
            change the input layer of the plugin to given layer, defaults to not
            changing the selected layer
        '''
        if self.pluginIsActive:
            return

        # initialize and show main widget
        if not self.mainwidget:
            # Create the dockwidget (after translation) and keep reference
            self.mainwidget = MainWidget()

        # connect to provide cleanup on closing of dockwidget
        self.mainwidget.closingWidget.connect(self.onClosePlugin)
        if layer:
            self.mainwidget.change_layer(layer)
        self.mainwidget.show()

