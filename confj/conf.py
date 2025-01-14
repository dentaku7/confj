import json
import os
import pathlib
from typing import Optional

from .exceptions import ConfigLoadException, NoConfigOptionError, \
    ConfigException
from . import const


class ConfigData:
    def __init__(self, data=None):
        self._data = data or {}

    def __getattr__(self, item: str):
        if item in self._data:
            return self._data.get(item)
        raise NoConfigOptionError('No such config option: {}'.format(item))

    def __getitem__(self, key):
        try:
            return self._data[key]
        except KeyError:
            raise NoConfigOptionError('No such config option: {}'.format(key))

    def c_data(self):
        container = None
        if isinstance(self._data, dict):
            container = dict()
            for key, value in self._data.items():
                if isinstance(value, ConfigData):
                    container[key] = value.c_data()
                else:
                    container[key] = value
        if isinstance(self._data, list):
            container = []
            for value in self._data:
                if isinstance(value, ConfigData):
                    container.append(value.c_data())
                else:
                    container.append(value)
        if container is None:
            container = self._data
        return container

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except NoConfigOptionError:
            return default

    def c_keys(self):
        return sorted(list(self._data.keys()))

    def c_items(self):
        if isinstance(self._data, dict):
            return self._data.items()
        raise ConfigException('Called "c_items" on non-dict config option')

    def c_format(self):
        import pprint
        return pprint.pformat(self.c_data(), indent=2)

    def c_pprint(self):
        import pprint
        return pprint.pprint(self.c_data(), indent=2)

    def c_validate(self, schema, do_raise=False):
        try:
            from jsonschema import validate, ValidationError
        except ImportError:
            raise ImportError(
                'Cannot find "jsonschema" package. Either install it manually '
                'with pip, or install confj with validation option: '
                'pip install confj[validation]')
        try:
            validate(self.c_data(), schema)
            return True
        except ValidationError:
            if do_raise:
                raise
            return False


class Config(ConfigData):
    def __init__(self, default_config_path=None, autoload=False):
        super(Config, self).__init__()
        self.default_config_path = default_config_path
        if autoload:
            self.load()

    def load(self, config_path=None):
        path = pathlib.Path(self._select_config_path(config_path))
        if not path.exists():
            raise ConfigLoadException('Path "{}" does not exist'.format(path))
        if path.is_dir():
            return self._load_from_dir(path)
        if path.is_file():
            return self._load_from_file(path)
        raise ConfigLoadException('Expected path {} to be file or '
                                  'directory'.format(path))

    def _select_config_path(self, config_path: Optional[str] = None) -> str:
        if config_path:
            return config_path
        if self.default_config_path:
            return self.default_config_path
        env_config_path = os.environ.get(const.ENV_CONF_PATH_NAME)
        if env_config_path:
            return env_config_path
        raise ConfigException('Please provide path to load config from')

    def _load_from_file(self, file_path):
        self._data = json.loads(file_path.read_text())

    def _load_from_dir(self, dir_path: pathlib.Path):
        for file in dir_path.iterdir():
            if not file.is_file():
                continue
            config_name = file.stem
            file_contents = file.read_text()
            if not file_contents.strip():
                self._data[config_name] = ''
            else:
                config_data = json.loads(file.read_text())
                self.add_subconfig(config_name, config_data)

    def add_subconfig(self, name, config_data):
        if name in self._data:
            raise ConfigException('Config already contains "{}" option!'.format(
                name))
        self._data[name] = ConfigData(config_data)
