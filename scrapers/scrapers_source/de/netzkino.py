# -*- coding: UTF-8 -*-
import json
import urllib.parse
import requests,re
from resources.lib.requestHandler import cRequestHandler
from scrapers.modules import cleantitle, dom_parser, source_utils
from resources.lib.control import getSetting
from resources.lib.utils import getExtIDS
from resources.lib.tools import logger, cParser
import xbmcgui

SITE_IDENTIFIER = 'netzkino'
SITE_DOMAIN = 'netzkino.de'
SITE_NAME = 'NETZKINO'


NETZKINO_GRAPHQL_ENDPOINT = 'https://data.netzkino.de/netzkino/graphql'
NETZKINO_SEARCH_HASH = 'e7f141530416887b1faa663dbdd468534c6639e47886e8156686afd9a0f81d76'
NETZKINO_OPERATION_NAME = 'Search'


class source:
    def __init__(self):
        self.priority = 1
        self.language = ['de']
        self.domain = getSetting('provider.' + SITE_IDENTIFIER + '.domain', SITE_DOMAIN)
        self.base_link = 'https://' + self.domain
        self.search_api = NETZKINO_GRAPHQL_ENDPOINT
        self.get_link = 'movie/load-stream/%s/%s?'
        self.playurl = 'https://www.netzkino.de/watch/%s'
        self.sources = []

    def _get_movie_details_by_id(self, content_id):

        if 1==1:
            sDetailUrl = f"https://www.netzkino.de/details/{content_id}"
            response = requests.get(sDetailUrl)
            response.raise_for_status()
            sHtmlContent= response.text
            if not sHtmlContent:
                return None
            regex = r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>'
            match = re.search(regex, sHtmlContent, re.DOTALL)
            json_string = match.group(1)

            try:
                data = json.loads(json_string)
                queries = data.get('props', {}).get('__dehydratedState', {}).get('queries', [])
                movie_query_state = next(
                    (q.get('state', {}) for q in queries
                     if q.get('queryKey', [''])[0] == 'MovieDetails'),
                    {}
                )
                movie_details = movie_query_state.get('data', {}).get('data', {}).get('movie')

                if not movie_details:
                    return None

                title = movie_details.get('title')
                year = movie_details.get('productionYear')
                pmd_url = movie_details.get('videoSource', {}).get('pmdUrl')

                if pmd_url:
                    return {
                        'pmdUrl': pmd_url,
                        'title': title,
                        'releaseYear': str(year) if year is not None else None
                    }
                return None

            except (json.JSONDecodeError, KeyError) as e:
                return None


    def _build_graphql_search_url(self, query_text):

        extensions = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": NETZKINO_SEARCH_HASH
            }
        }

        variables = {
            "text": query_text
        }
        encoded_extensions = urllib.parse.quote(json.dumps(extensions))
        encoded_variables = urllib.parse.quote(json.dumps(variables))

        search_url = (
            f"{NETZKINO_GRAPHQL_ENDPOINT}?"
            f"extensions={encoded_extensions}&"
            f"variables={encoded_variables}&"
            f"operationName={NETZKINO_OPERATION_NAME}"
        )

        return search_url

    def run(self, titles, year, season=0, episode=0, imdb='', hostDict=None):

        if season > 0:
            return self.sources

        if not titles:
            return self.sources

        ascii_titles = [t for t in titles if all(ord(c) < 128 for c in t)]

        if ascii_titles:
            sSearchText = min(ascii_titles, key=len)
        else:
            sSearchText = min(titles, key=len)

        sSearchText = sSearchText.lower()

        if not sSearchText:
            return self.sources

        try:
            sUrl = self._build_graphql_search_url(sSearchText)
            response = requests.get(sUrl)
            response.raise_for_status()
            data = response.json()
            sJsonContent = data

            if not data or 'data' not in data:
                return self.sources
            results = data.get('data', {}).get('search', {}).get('nodes', [])
            if not isinstance(results, list):
                return self.sources

            for movie_node in results:
                movie_id = movie_node.get('id')

                if not movie_id:
                    continue
                full_movie_details = self._get_movie_details_by_id(movie_id)

                if not full_movie_details:
                    continue
                api_title = cleantitle.get(full_movie_details.get('title', ''))
                api_year = full_movie_details.get('releaseYear')
                stream_url = full_movie_details.get('pmdUrl')

                title_match = api_title

                if title_match:
                    year_match = (not api_year or str(api_year) == str(year))

                    if not year_match:
                        continue
                    if stream_url:
                        CDN_PREFIX_PMD = 'https://pmd.netzkino-seite.netzkino.de/'
                        final_stream_url = CDN_PREFIX_PMD + stream_url
                        self.sources.append({
                            'source': 'Netzkino',
                            'quality': 'HD',
                            'language': 'de',
                            'url': final_stream_url,
                            'direct': True
                        })

        except requests.exceptions.HTTPError as e:
            logger.error(f"[NETZKINO] FEHLER bei HTTP-Anfrage: {e}")
        except json.JSONDecodeError:
            logger.error("[NETZKINO] FEHLER: Konnte API-Antwort nicht als JSON parsen. (Antwort war nicht gültiges JSON)")
        except KeyError as e:
            logger.error(f"[NETZKINO] FEHLER bei JSON-Navigation: Schlüssel '{e}' fehlt oder Struktur unerwartet.")
        except Exception as e:
            logger.error(f"[NETZKINO] Kritischer Fehler im RUN-Ablauf: {e}")
        return self.sources


    def resolve(self, url):
        return url