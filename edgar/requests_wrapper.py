import requests
import os
import calendar
from cachecontrol import CacheControl
from cachecontrol.heuristics import BaseHeuristic
from cachecontrol.caches.file_cache import FileCache
from datetime import datetime, timedelta
from email.utils import parsedate, formatdate


CACHE_DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data', 'cache')


class AlwaysCache(BaseHeuristic):

    def update_headers(self, response):
        # Don't let the header determine if this is cached
        # Always cache it!
        date = parsedate(response.headers['date'])
        expires = datetime(*date[:6]) + timedelta(weeks=1)
        return {
            'expires': formatdate(calendar.timegm(expires.timetuple())),
            'cache-control': 'public',
        }


class GetRequest:

    # XXX Need to figure out a better caching strategy
    SESSION = CacheControl(requests.Session(),
                           heuristic=AlwaysCache(),
                           cache=FileCache(CACHE_DATA_PATH, forever=True))

    def __init__(self, url, cache=True):

        if cache:
            _requests = self.SESSION
        else:
            _requests = requests

        response = _requests.get(url, headers={'Accept-Encoding': 'gzip,deflate,sdch'})
        response.encoding = 'utf-8'
        if response.status_code != requests.codes.ok:
            raise RequestException('{}: {}'.format(response.status_code, response.text))

        self.response = response


class RequestException(Exception):
    pass
