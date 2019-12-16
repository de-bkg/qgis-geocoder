# -*- coding: utf-8 -*-
import json
import os, sys, copy
from os.path import expanduser

DEFAULT_FILE = os.path.join(expanduser("~"), "bkg_geocoder.cfg")
DEFAULT_URL = 'http://sg.geodatenzentrum.de/gdz_geokodierung__{key}/geosearch'


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Config(object):
    __metaclass__ = Singleton

    _default = {
        'url': DEFAULT_URL,
        'api_key': ''
    }

    _config = {}

    # write changed config instantly to file
    _write_instantly = True

    def __init__(self):
        self.config_file = DEFAULT_FILE
        self._callbacks = {}
        self.active_coord = (0, 0)
        if os.path.exists(self.config_file):
            self.read()
            # add missing Parameters
            changed = False
            for k, v in self._default.items():
                if k not in self._config:
                    self._config[k] = v
                    changed = True
            if changed:
                self.write()

        # write default config, if file doesn't exist yet
        else:
            self._config = self._default.copy()
            self.write()

    def read(self, config_file=None):
        if config_file is None:
            config_file = self.config_file
        try:
            with open(config_file, 'r') as f:
                self._config = json.load(f)
        except:
            self._config = self._default.copy()
            print('Error while loading config. Using default values.')

    def write(self, config_file=None):
        if config_file is None:
            config_file = self.config_file

        with open(config_file, 'w') as f:
            config_copy = self._config.copy()
            # pretty print to file
            json.dump(config_copy, f, indent=4, separators=(',', ': '))

    # access stored config entries like fields
    def __getattr__(self, name):
        if name in self.__dict__:
            return self.__dict__[name]
        elif name in self._config:
            return self._config[name]
        raise AttributeError

    def __setattr__(self, name, value):
        if name in self._config:
            self._config[name] = value
            if self._write_instantly:
                self.write()
            if name in self._callbacks:
                for callback in self._callbacks[name]:
                    callback(value)
        else:
            self.__dict__[name] = value

    def __repr__(self):
        return repr(self._config)

    def on_change(self, attribute, callback):
        if attribute not in self._callbacks:
            self._callbacks[attribute] = []
        self._callbacks[attribute].append(callback)

    def remove_listeners(attribute):
        if attribute in self._callbacks:
            self._callbacks.pop(attribute)
