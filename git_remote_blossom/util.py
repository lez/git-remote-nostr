import json
import os
import sys


def stdout(line):
    """
    Write line to standard output.
    """
    sys.stdout.write(line)
    sys.stdout.flush()


def stderr(line):
    """
    Write line to standard error.
    """
    sys.stderr.write(line)
    sys.stderr.flush()


def readline():
    """
    Read a line from standard input.
    """
    return sys.stdin.readline().strip()  # remove trailing newline


def stdout_to_binary():
    """
    Ensure that stdout is in binary mode on windows
    """
    if sys.platform == 'win32':
        import msvcrt
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)


class Level(object):
    """
    A class for severity levels.
    """

    ERROR = 0
    INFO = 1
    DEBUG = 2


class Poison(object):
    """
    A poison pill.

    Instances of this class can be used as sentinel objects to communicate
    termination requests to processes.
    """

    def __init__(self, message=None):
        self.message = message


class Config(object):
    """
    A class to manage configuration data.
    """

    def __init__(self, filename):
        with open(filename) as f:
            self._settings = json.load(f)

    def __getitem__(self, key):
        """
        Return the setting corresponding to key.

        Raises KeyError if the config file is missing the key.
        """
        return self._settings[key]
