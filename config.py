# -*- coding: utf-8 -*-
'''
***************************************************************************
    config.py
    ---------------------
    Date                 : October 2018
    Copyright            : (C) 2018 by Christoph Franke
    Email                : franke at ggr-planung dot de
***************************************************************************
*                                                                         *
*   This program is free software: you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 3 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************

manages saving and loading settings made by user in UI
contains main paths to additional data
'''

__author__ = 'Christoph Franke'
__date__ = '30/10/2018'

import json
import os
from os.path import expanduser

from .geocoder.bkg_geocoder import URL

path = os.path.dirname(__file__)

VERSION = '1.3'

# data paths
UI_PATH = os.path.join(path, 'interface', 'ui')
ICON_PATH = os.path.join(path, 'interface', 'ui', 'icons')
STYLE_PATH = os.path.join(path, 'interface', 'styles')

# url to help website, left out trailing 'file://', other wise webbrowser won't
# open tags or pass query params whyever
HELP_URL = f'{path}/help/Benutzerhandbuch.html'.replace('\\', '/')

# path to config file location
DEFAULT_FILE = os.path.join(expanduser("~"), "bkg_geocoder.cfg")
DEFAULT_STYLE = os.path.join(
    STYLE_PATH, 'BKG_Layerstil_nach_Trefferbewertung.qml')


class Singleton(type):
    '''
    singleton class
    '''
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(
                *args, **kwargs)
        return cls._instances[cls]


class Config(object):
    '''
    singleton config, store and load settings from a json config file

    Attributes
    ----------
    default : dict
        default values the config file is filled with on creation
    write_instantly : bool
        write changes to configuration instantly to set file if True
    '''
    __metaclass__ = Singleton

    default = {
        'url': URL,
        'api_key': '',
        'api_url': '',
        'use_api_url': False,
        'logic_link': 'OR',
        'selected_features_only': False,
        'projection': 'EPSG:25832',
        'use_rs': False,
        'debug': False,
        'fuzzy': False,
        'rs': '',
        'output_style': DEFAULT_STYLE,
        'result_fields': [],
        'load_background': True
    }

    _config = {}

    # write changed config instantly to file
    write_instantly = True

    def __init__(self):
        self.config_file = DEFAULT_FILE
        self._callbacks = {}
        self.active_coord = (0, 0)
        if os.path.exists(self.config_file):
            self.read()
            # add missing Parameters
            changed = False
            for k, v in self.default.items():
                if k not in self._config:
                    self._config[k] = v
                    changed = True
            if changed:
                self.write()

        # write default config, if file doesn't exist yet
        else:
            self._config = self.default.copy()
            self.write()

    def read(self, config_file: str = None):
        '''
        read configuration from file

        Parameters
        ----------
        config_file : str, optional
            path to configuration file (json), defaults to currently set file
        '''
        if config_file is None:
            config_file = self.config_file
        try:
            with open(config_file, 'r') as f:
                self._config = json.load(f)
        except:
            self._config = self.default.copy()
            print('Error while loading config. Using default values.')

    def write(self, config_file: str = None):
        '''
        write current configuration to file

        Parameters
        ----------
        config_file : str, optional
            path to configuration file (json), defaults to currently set file
        '''
        if config_file is None:
            config_file = self.config_file

        with open(config_file, 'w') as f:
            config_copy = self._config.copy()
            # pretty print to file
            json.dump(config_copy, f, indent=4, separators=(',', ': '))

    def __getattr__(self, name: str):
        '''access stored config entries like fields'''
        if name in self.__dict__:
            return self.__dict__[name]
        elif name in self._config:
            return self._config[name]
        raise AttributeError

    def __setattr__(self, name: str, value: object):
        '''set config entries like fields'''
        if name in self._config:
            self._config[name] = value
            if self.write_instantly:
                self.write()
            if name in self._callbacks:
                for callback in self._callbacks[name]:
                    callback(value)
        else:
            self.__dict__[name] = value

    def __repr__(self):
        return repr(self._config)

    def on_change(self, attribute: str, callback: object):
        '''
        register callback function to be called on configuration
        attribute change

        Parameters
        ----------
        attribute : str
            name of the attribute
        callback : function
            function to call if value of attribute has changed,
            function should expect the value as a parameter
        '''
        if attribute not in self._callbacks:
            self._callbacks[attribute] = []
        self._callbacks[attribute].append(callback)

    def remove_listeners(self, attribute: str):
        '''
        remove all callback functions of an configuration attribute

        Parameters
        ----------
        attribute : str
            name of the attribute
        '''
        if attribute in self._callbacks:
            self._callbacks.pop(attribute)
