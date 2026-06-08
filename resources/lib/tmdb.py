

#2022-11-05
# edit 2023-02-23

from __future__ import print_function
import json, re
from urllib.parse import quote_plus
from resources.lib.requestHandler import cRequestHandler
from resources.lib.control import getSetting

class cTMDB:
    TMDB_GENRES = {12: 'Abenteuer', 14: 'Fantasy', 16: 'Animation', 18: 'Drama', 27: 'Horror', 28: 'Action', 35: 'KomÃ¶die', 36: 'Historie', 37: 'Western', 53: 'Thriller', 80: 'Krimi', 99: 'Dokumentarfilm', 878: 'Science Fiction', 9648: 'Mystery', 10402: 'Musik', 10749: 'Liebesfilm', 10751: 'Familie', 10752: 'Kriegsfilm', 10759: 'Action & Adventure', 10762: 'Kids', 10763: 'News', 10764: 'Reality', 10765: 'Sci-Fi & Fantasy', 10766: 'Soap', 10767: 'Talk', 10768: 'War & Politics', 10770: 'TV-Film'}
    URL = 'https://api.themoviedb.org/3/'
    URL_TRAILER = 'plugin://plugin.video.youtube/play/?video_id=%s'

    def __init__(self, api_key='', lang='de'):
        self.api_key = (api_key or getSetting('api.tmdb')).strip()
        self.lang = lang
        self.poster = 'https://image.tmdb.org/t/p/%s' % 'w342' #cConfig().getSetting('poster_tmdb')
        self.fanart = 'https://image.tmdb.org/t/p/%s' % 'w1280'#cConfig().getSetting('backdrop_tmdb')
        self.mediaType = ''
        self.searchDoku = getSetting('search.doku') or 'false'

    def search_movie_name(self, name, year='', page=1, advanced='false'):
        name = re.sub(" +", " ", name)
        if year:
            term = quote_plus(name) + '&year=' + str(year)
        else:
            term = quote_plus(name)
        meta = self._call('search/movie', 'query=' + term + '&page=' + str(page))
        if 'errors' not in meta and 'status_code' not in meta:
            if 'total_results' in meta and meta['total_results'] == 0 and year:
                meta = self.search_movie_name(name, '')
            if 'total_results' in meta and meta['total_results'] != 0:
                movie = ''
                if meta['total_results'] == 1:
                    movie = meta['results'][0]
                else:
                    for searchMovie in meta['results']:
                        if searchMovie['genre_ids']:
                            if self.searchDoku == 'false' and 99 in searchMovie['genre_ids']: continue
                            if searchMovie['title'].lower() == name.lower():
                                movie = searchMovie
                                break
                    if not movie:
                        for searchMovie in meta['results']:
                            if searchMovie['genre_ids']:
                                if self.searchDoku == 'false' and 99 in searchMovie['genre_ids']: continue
                                if year:
                                    if 'release_date' in searchMovie and searchMovie['release_date']:
                                        release_date = searchMovie['release_date']
                                        yy = release_date[:4]
                                        if int(year) - int(yy) > 1:
                                            continue
                                movie = searchMovie
                                break
                    if not movie:
                        movie = meta['results'][0]
                if advanced == 'true':
                    tmdb_id = movie['id']
                    meta = self.search_movie_id(tmdb_id)
                else:
                    meta = movie
        else:
            meta = {}
        return meta

    def search_movie_id(self, movie_id, append_to_response='append_to_response=alternative_titles,credits'):
        result = self._call('movie/' + str(movie_id), append_to_response)
        result['tmdb_id'] = movie_id
        return result

    # def search_movie_imdb_id(self, movie_id, append_to_response='append_to_response=trailers,credits'):
    #     result = self._call('movie/' + str(movie_id), append_to_response)
    #     result['tmdb_id'] = movie_id
    #     return result


    def search_tvshow_name(self, name, year='', page=1, genre='', advanced='false'):
        name = name.lower()
        if '- staffel' in name:
            name = re.sub(r'\s-\s\wtaffel[^>]([1-9\-]+)', '', name)
        elif 'staffel' in name:
            name = re.sub(r'\s\wtaffel[^>]([1-9\-]+)', '', name)
        if year:
            term = quote_plus(name) + '&year=' + str(year)
        else:
            term = quote_plus(name)
        meta = self._call('search/tv', 'query=' + term + '&page=' + str(page))
        if 'errors' not in meta and 'status_code' not in meta:
            if 'total_results' in meta and meta['total_results'] == 0 and year:
                meta = self.search_tvshow_name(name, '')
            if 'total_results' in meta and meta['total_results'] != 0:
                movie = ''
                if meta['total_results'] == 1:
                    movie = meta['results'][0]
                else:
                    for searchMovie in meta['results']:
                        if genre == '' or genre in searchMovie['genre_ids']:
                            movieName = searchMovie['name']
                            if movieName.lower() == name.lower():
                                movie = searchMovie
                                break
                    if not movie:
                        for searchMovie in meta['results']:
                            if genre and genre in searchMovie['genre_ids']:
                                if year:
                                    if 'release_date' in searchMovie and searchMovie['release_date']:
                                        release_date = searchMovie['release_date']
                                        yy = release_date[:4]
                                        if int(year) - int(yy) > 1:
                                            continue
                                movie = searchMovie
                                break
                    if not movie:
                        movie = meta['results'][0]
                if advanced == 'true':
                    tmdb_id = movie['id']
                    meta = self.search_tvshow_id(tmdb_id)
                else:
                    meta = movie
        else:
            meta = {}
        return meta

    def search_tvshow_id(self, show_id, append_to_response='append_to_response=external_ids,alternative_titles,credits'):
        result = self._call('tv/' + str(show_id), append_to_response)
        result['tmdb_id'] = show_id
        return result

    def get_meta(self, media_type, name, imdb_id='', tmdb_id='', year='', season='', episode='', advanced='false'):
        name = re.sub(" +", " ", name)
        meta = {}
        if media_type == 'movie':
            if tmdb_id:
                meta = self.search_movie_id(tmdb_id)
            elif name:
                meta = self.search_movie_name(name, year, advanced=advanced)
        elif media_type == 'tvshow':
            if tmdb_id:
                meta = self.search_tvshow_id(tmdb_id)
            elif name:
                meta = self.search_tvshow_name(name, year, advanced=advanced)
        if meta and 'id' in meta:
            meta.update({'mediatype': media_type})
            meta = self._formatSuper(meta, name)
        return meta

    def getUrl(self, url, page=1, term=''):
        try:
            if term:
                term = term + '&page=' + str(page)
            else:
                term = 'page=' + str(page)
            result = self._call(url, term)
        except:
            return False
        return result

    def _call(self, action, append_to_response=''):
        url = '%s%s?language=%s&api_key=%s&include_adult=false' % (self.URL, action, self.lang, self.api_key) # &region=DE&vote_count.gte=10
        if append_to_response:
            url += '&%s' % append_to_response
        # if 'person' in url:
        #     url = url.replace('&page=', '')
        oRequestHandler = cRequestHandler(url, ignoreErrors=True)
        name = oRequestHandler.request()
        if not name:
            return {}
        try:
            data = json.loads(name)
        except (TypeError, ValueError):
            return {}
        if 'status_code' in data and data['status_code'] == 34:
            return {}
        return data

    def getGenresFromIDs(self, genresID):
        sGenres = []
        for gid in genresID:
            genre = self.TMDB_GENRES.get(gid)
            if genre:
                sGenres.append(genre)
        return sGenres

    def getLanguage(self, Language):
        iso_639 = {'en': 'English', 'de': 'German', 'fr': 'French', 'it': 'Italian', 'nl': 'Nederlands', 'sv': 'Swedish', 'cs': 'Czech', 'da': 'Danish', 'fi': 'Finnish', 'pl': 'Polish', 'es': 'Spanish', 'el': 'Greek', 'tr': 'Turkish', 'uk': 'Ukrainian', 'ru': 'Russian', 'kn': 'Kannada', 'ga': 'Irish', 'hr': 'Croatian', 'hu': 'Hungarian', 'ja': 'Japanese', 'no': 'Norwegian', 'id': 'Indonesian', 'ko': 'Korean', 'pt': 'Portuguese', 'lv': 'Latvian', 'lt': 'Lithuanian', 'ro': 'Romanian', 'sk': 'Slovak', 'sl': 'Slovenian', 'sq': 'Albanian', 'sr': 'Serbian', 'th': 'Thai', 'vi': 'Vietnamese', 'bg': 'Bulgarian', 'fa': 'Persian', 'hy': 'Armenian', 'ka': 'Georgian', 'ar': 'Arabic', 'af': 'Afrikaans', 'bs': 'Bosnian', 'zh': 'Chinese', 'cn': 'Chinese', 'hi': 'Hindi'}
        if Language in iso_639:
            return iso_639[Language]
        else:
            return Language

    def get_meta_episode(self, media_type, name, tmdb_id='', season='', episode='', advanced='false'):
        meta = {}
        if media_type == 'episode' and tmdb_id and season and episode:
            url = '%stv/%s/season/%s/episode/%s?api_key=%s&language=de&include_adult=false' % (self.URL, tmdb_id, season, episode, self.api_key)
            if advanced == 'true': url = url + '&append_to_response=external_ids,videos,credits'
            Data = cRequestHandler(url, ignoreErrors=True).request()
            if Data:
                meta = json.loads(Data)
                #meta.update({'episode': episode})
                meta = self._format_episodes(meta, name)
                return meta

        else:
            return {}

    def get_meta_seasons(self, tmdb_id='', season='', advanced='false'):
        meta = {}
        if tmdb_id and season:
            url = '%stv/%s/season/%s?api_key=%s&language=de&include_adult=false' % (self.URL, tmdb_id, season, self.api_key)
            Data = cRequestHandler(url, ignoreErrors=True).request()
            if Data:
                meta = json.loads(Data)
        if 'id' in meta:
            _meta = {}
            if 'name' in meta and meta['name']:
                _meta['name'] = meta['name']
            if 'poster_path' in meta and meta['poster_path']:
                _meta['poster'] = self.poster + str(meta['poster_path'])
            if 'air_date' in meta and meta['air_date']:
                _meta['premiered'] = meta['air_date']
            if 'episodes' in meta and meta['episodes']:
                _meta['number_of_episodes'] = len(meta['episodes'])
                _meta['episodes'] = meta['episodes']
            if 'season_number' in meta and meta['season_number']:
                _meta['season'] = meta['season_number']
            if 'overview' in meta:
                _meta['plot'] = meta['overview']

            return _meta
        else:
            return {}

    def _format_episodes(self, meta, name):
        _meta = {}
        if 'air_date' in meta:
            #_meta['aired'] = meta['air_date']
            _meta['premiered'] = meta['air_date']
        if 'episode_number' in meta:
            _meta['episode'] = meta['episode_number']
        if 'name' in meta:
            _meta['title'] = meta['name']
        if 'overview' in meta:
            _meta['plot'] = meta['overview']
        if 'production_code' in meta:
            _meta['code'] = str(meta['production_code'])
        if 'season_number' in meta:
            _meta['season'] = meta['season_number']
        if 'still_path' in meta and meta['still_path'] != None:
            _meta['cover_url'] = self.poster + meta['still_path']
            _meta['poster'] = _meta['cover_url']
        if 'vote_average' in meta:
            _meta['rating'] = meta['vote_average']
        if 'vote_count' in meta:
            _meta['votes'] = meta['vote_count']
        if 'crew' in meta:
            _meta['writer'] = ''
            _meta['director'] = ''
            _meta['cast'] = ''
            for crew in meta['crew']:
                if crew['department'] == 'Directing':
                    if _meta['director'] != '':
                        _meta['director'] += ' / '
                    _meta['director'] += '%s: %s' % (crew['job'], crew['name'])
                elif crew['department'] == 'Writing':
                    if _meta['writer'] != '':
                        _meta['writer'] += ' / '
                    _meta['writer'] += '%s: %s' % (crew['job'], crew['name'])
        if 'guest_stars' in meta: #TODO
            licast = []
            for c in meta['guest_stars']:
                licast.append((c['name'], c['character'], self.poster + str(c['profile_path'])))
            _meta['cast'] = licast

        return _meta

    # def _format(self, meta, name):
    #     _meta = {}
    #     _meta['genre'] = ''
    #     if 'id' in meta:
    #         _meta['tmdb_id'] = meta['id']
    #     if 'backdrop_path' in meta and meta['backdrop_path']:
    #         _meta['backdrop_url'] = self.fanart + str(meta['backdrop_path'])
    #     if 'original_language' in meta and meta['original_language']:
    #         _meta['country'] = self.getLanguage(meta['original_language'])
    #     if 'original_title' in meta and meta['original_title']:
    #         _meta['originaltitle'] = meta['original_title']
    #     elif 'original_name' in meta and meta['original_name']:
    #         _meta['originaltitle'] = meta['original_name']
    #     if 'overview' in meta and meta['overview']:
    #         _meta['plot'] = meta['overview']
    #     if 'poster_path' in meta and meta['poster_path']:
    #         _meta['cover_url'] = self.poster + str(meta['poster_path'])
    #     if 'release_date' in meta and meta['release_date']:
    #         _meta['premiered'] = meta['release_date']
    #     elif 'first_air_date' in meta and meta['first_air_date']:
    #         _meta['premiered'] = meta['first_air_date']
    #     if 'premiered' in _meta and _meta['premiered'] and len(_meta['premiered']) == 10:
    #         _meta['year'] = int(_meta['premiered'][:4])
    #     if 'budget' in meta and meta['budget']:
    #         _meta['budget'] = "{:,} $".format(meta['budget'])
    #     if 'revenue' in meta and meta['revenue']:
    #         _meta['revenue'] = "{:,} $".format(meta['revenue'])
    #     if 'status' in meta and meta['status']:
    #         _meta['status'] = meta['status']
    #     duration = 0
    #     if 'runtime' in meta and meta['runtime']:
    #         duration = int(meta['runtime'])
    #     elif 'episode_run_time' in meta and meta['episode_run_time']:
    #         duration = int(meta['episode_run_time'][0])
    #     if duration < 300:
    #         duration *= 60
    #     if duration > 1:
    #         _meta['duration'] = duration
    #     if 'tagline' in meta and meta['tagline']:
    #         _meta['tagline'] = meta['tagline']
    #     if 'vote_average' in meta and meta['vote_average']:
    #         _meta['rating'] = meta['vote_average']
    #     if 'vote_count' in meta and meta['vote_count']:
    #         _meta['votes'] = meta['vote_count']
    #     if 'genres' in meta and meta['genres']:
    #         for genre in meta['genres']:
    #             if _meta['genre'] == '':
    #                 _meta['genre'] += genre['name']
    #             else:
    #                 _meta['genre'] += ' / ' + genre['name']
    #     elif 'genre_ids' in meta and meta['genre_ids']:
    #         genres = self.getGenresFromIDs(meta['genre_ids'])
    #         for genre in genres:
    #             if _meta['genre'] == '':
    #                 _meta['genre'] += genre
    #             else:
    #                 _meta['genre'] += ' / ' + genre
    #     if 'production_companies' in meta and meta['production_companies']:
    #         _meta['studio'] = ''
    #         for studio in meta['production_companies']:
    #             if _meta['studio'] == '':
    #                 _meta['studio'] += studio['name']
    #             else:
    #                 _meta['studio'] += ' / ' + studio['name']
    #     if 'credits' in meta and meta['credits']:
    #         strmeta = str(meta['credits'])
    #         listCredits = eval(strmeta)
    #         casts = listCredits['cast']
    #         crews = []
    #         if len(casts) > 0:
    #             licast = []
    #             if 'crew' in listCredits:
    #                 crews = listCredits['crew']
    #             if len(crews) > 0:
    #                 _meta['credits'] = "{'cast': " + str(casts) + ", 'crew': " + str(crews) + "}"
    #                 for cast in casts:
    #                     licast.append((cast['name'], cast['character'], self.poster + str(cast['profile_path']), str(cast['id'])))
    #                 _meta['cast'] = licast
    #             else:
    #                 _meta['credits'] = "{'cast': " + str(casts) + '}'
    #         if len(crews) > 0:
    #             _meta['writer'] = ''
    #             for crew in crews:
    #                 if crew['job'] == 'Director':
    #                     _meta['director'] = crew['name']
    #                 elif crew['department'] == 'Writing':
    #                     if _meta['writer'] != '':
    #                         _meta['writer'] += ' / '
    #                     _meta['writer'] += '%s: %s' % (crew['job'], crew['name'])
    #                 elif crew['department'] == 'Production' and 'Producer' in crew['job']:
    #                     if _meta['writer'] != '':
    #                         _meta['writer'] += ' / '
    #                     _meta['writer'] += '%s: %s' % (crew['job'], crew['name'])
    #     if 'trailers' in meta and meta['trailers']:
    #         if 'youtube' in meta['trailers']:
    #             trailers = ''
    #             for t in meta['trailers']['youtube']:
    #                 if t['type'] == 'Trailer':
    #                     trailers = self.URL_TRAILER % t['source']
    #             if trailers:
    #                 _meta['trailer'] = trailers
    #     elif 'videos' in meta and meta['videos']:
    #         if 'results' in meta['videos']:
    #             trailers = ''
    #             for t in meta['videos']['results']:
    #                 if t['type'] == 'Trailer' and t['site'] == 'YouTube':
    #                     trailers = self.URL_TRAILER % t['key']
    #             if trailers:
    #                 _meta['trailer'] = trailers
    #     return _meta


    def search_term(self, mediaType, name, page=1):
        if not mediaType in ["movie", "tvshow", "person"]:
            return [], 0
        urlType = mediaType if not mediaType == 'tvshow' else 'tv'
        try:
            meta = self._call('search/'+ urlType, 'query=' + quote_plus(name) + '&page=' + str(page))
            if not meta or 'errors' in meta or 'status_code' in meta: return [], 0
            elif 'total_results' in meta and meta['total_results'] == 0: return [], 0
            else:
                list = []
                if urlType == 'person':
                    for i in meta['results']:
                        if i['known_for_department'] != "Acting": continue
                        poster = self.poster + str(i['profile_path']) if i['profile_path'] != None else None
                        popularity = int(str(i['popularity']).replace('.',''))
                        list.append({'id': i['id'], 'name': i['name'], "poster": poster, 'popularity': popularity})

                else:
                    for i in  meta['results']:
                        try:
                            if i['genre_ids']:
                                if self.searchDoku == 'false' and 99 in i['genre_ids']: continue
                            list.append(i['id'])
                        except:
                            pass
                return list, meta['total_pages']
        except Exception:
            return [], 0


    def search_credits(self, Type, id):
        # https://developers.themoviedb.org/3/people/get-person-combined-credits
        if not Type in ["combined_credits", "tv_credits", "movie_credits"]: return
        meta = self._call('person/' + str(id) + '/' + Type)
        meta = meta['cast']
        #meta = self._formatSuper(meta['cast'], '')
        list = []
        for i in meta:
            if i['genre_ids'] and self.searchDoku == 'false' and 99 in i['genre_ids']: continue
            if i['character'] and ('voice' or 'rumored' or 'uncredited') in i['character']: continue
            i.update({'popularity':int(str(i['popularity']).replace('.',''))})
            if Type == "movie_credits": i.update({'mediatype': 'movie'})
            elif Type == "tv_credits": i.update({'mediatype': 'tvshow'})
            list.append(i)
        return list


    def _formatSuper(self, meta, name):
        try:
            _meta = {}
            # ID
            # if meta['id'] == 479455:
            if 'id' in meta:
                _meta['tmdb_id'] = str(meta['id'])
            if  'external_ids' in meta:
                if meta['external_ids']['imdb_id']: _meta['imdbnumber'] = meta['external_ids']['imdb_id']
                if meta['external_ids']['tvdb_id']: _meta['tvdb_id'] = str(meta['external_ids']['tvdb_id'])
            if not 'imdbnumber' in _meta and 'imdb_id' in meta: _meta['imdbnumber'] = meta['imdb_id']

            if 'imdbnumber' in _meta: _meta['imdb_id'] = _meta['imdbnumber']
            try:
                _meta['mediatype'] = meta['mediatype'] if 'mediatype' in meta else None
                if not _meta['mediatype'] and 'media_type' in meta: _meta['mediatype'] = meta['media_type']
            except:
                print(meta['media_type'])
                pass
            if 'backdrop_path' in meta and meta['backdrop_path']:
                _meta['fanart'] = self.fanart + str(meta['backdrop_path'])
                _meta['backdrop_url'] = self.fanart + str(meta['backdrop_path'])
            if 'original_language' in meta and meta['original_language']:
                _meta['originallanguage'] = self.getLanguage(meta['original_language'])
            if 'original_title' in meta and meta['original_title']:
                _meta['originaltitle'] = meta['original_title']
            elif 'original_name' in meta and meta['original_name']:
                _meta['originaltitle'] = meta['original_name']
            if 'title' in meta and meta['title']:
                _meta['title'] = meta['title']
            elif 'name' in meta and meta['name']:
                _meta['title'] = meta['name']
            else:
                _meta['title'] = _meta['originaltitle']

            # if _meta['tmdb_id'] == '48866':
            #     import pydevd
            #     pydevd.settrace('localhost', port=12345, stdoutToServer=True, stderrToServer=True)

            # if 'overview' in meta and len(meta['overview'].strip()) > 5 :
            #     _meta['plot'] = meta['overview']
            # else:

            urlType = _meta['mediatype'] if _meta['mediatype'] == 'movie' else 'tv'
            overviews = self._call(urlType + '/' + str(_meta['tmdb_id']) + '/translations')
            # overview = overviews['translations'][0]['data']['overview']
            if len(overviews['translations']) > 0:
                overviews = overviews['translations']
                for overview in overviews:
                    if overview['name'] == "Deutsch" or  overview['iso_639_1'] == "de": #  or  overview['name'] == "English":
                        _meta.update({'plot': overview['data']['overview']})
                        break
                    elif not 'plot' in _meta and not 'overview' in _meta and overview['name'] == "English":
                        _meta.update({'plot': overview['data']['overview']})

            if not 'plot' in _meta:
                if 'overview' in meta and len(meta['overview'].strip()) > 5:
                    _meta['plot'] = meta['overview']
                else:
                    _meta['plot'] = ''

            if 'poster_path' in meta and meta['poster_path']:
                _meta['poster'] = self.poster + str(meta['poster_path'])
                _meta['cover_url'] = self.poster + str(meta['poster_path'])
            if 'release_date' in meta and meta['release_date']:
                _meta['premiered'] = meta['release_date']
            elif 'first_air_date' in meta and meta['first_air_date']:
                _meta['premiered'] = meta['first_air_date']
            if 'premiered' in _meta and _meta['premiered'] and len(_meta['premiered']) == 10:
                _meta['year'] = int(_meta['premiered'][:4])
            if 'budget' in meta and meta['budget']:
                _meta['budget'] = "{:,} $".format(meta['budget'])
            if 'revenue' in meta and meta['revenue']:
                _meta['revenue'] = "{:,} $".format(meta['revenue'])
            if 'status' in meta and meta['status']:
                _meta['status'] = meta['status']
            duration = 0
            if 'runtime' in meta and meta['runtime']:
                duration = int(meta['runtime'])
            elif 'episode_run_time' in meta and meta['episode_run_time']:
                duration = int(meta['episode_run_time'][0])
            if duration < 300:
                duration *= 60
            if duration > 1:
                _meta['duration'] = duration
            if 'tagline' in meta and meta['tagline']:
                _meta['tagline'] = meta['tagline']
            if 'vote_average' in meta and meta['vote_average']:
                _meta['rating'] = meta['vote_average']
            if 'vote_count' in meta and meta['vote_count']:
                _meta['votes'] = meta['vote_count']

            _meta['genre'] = ()
            if 'genres' in meta and meta['genres']:
                for genre in meta['genres']:
                     if 'name' in genre and genre['name']:
                        _meta['genre'] = _meta['genre'] + (genre['name'],)

            elif 'genre_ids' in meta and meta['genre_ids']:
                _meta['genre_ids'] = meta['genre_ids']
                genres = self.getGenresFromIDs(meta['genre_ids'])
                for genre in genres:
                    _meta['genre'] = _meta['genre'] + (genre,)

            if 'production_companies' in meta and meta['production_companies']:
                _meta['studio'] = ()
                for studio in meta['production_companies']:
                    _meta['studio'] = _meta['studio'] + (studio['name'],)

            if 'production_countries' in meta and meta['production_countries']:
                _meta['country'] = ()
                for country in meta['production_countries']:
                    _meta['country'] = _meta['country'] + (country['name'],)

            if 'credits' in meta and meta['credits']:
                # crews = []
                # casts = []
                strmeta = str(meta['credits'])
                listCredits = eval(strmeta)

                _meta['writer'] = ()
                _meta['director'] = ()
                if 'crew' in listCredits and len(listCredits['crew']) > 0:
                    crews = listCredits['crew']
                    for crew in crews:
                        if crew['job'] == 'Director':
                            _meta['director'] = _meta['director'] + (crew['name'],)
                        elif crew['department'] == 'Writing':
                            _meta['writer'] = _meta['writer'] + ('%s: %s' % (crew['job'], crew['name']),)
                        elif crew['department'] == 'Production' and 'Producer' in crew['job']:
                            _meta['writer'] = _meta['writer'] + ('%s: %s' % (crew['job'], crew['name']),)

                if 'cast' in listCredits and len(listCredits['cast']) > 0:
                    licast = []
                    casts = listCredits['cast']
                    for cast in casts:
                        # licast.append((cast['name'], cast['character'], self.poster + str(cast['profile_path']), str(cast['id'])))
                        licast.append(
                            ## {"name": cast['name'], "role": cast['character'], "thumbnail": self.poster + str(cast['profile_path']), 'order': str(cast['order'])}
                            {"name": cast['name'], "role": cast['character'], "thumbnail": self.poster + str(cast['profile_path']), 'order': int(cast['order'])}
                        )
                    _meta['cast'] = licast

                # if len(casts) > 0 and len(crews) > 0:
                #     _meta['credits'] = "{'cast': " + str(casts) + ", 'crew': " + str(crews) + "}"
                # elif len(casts) > 0:
                #     _meta['credits'] = "{'cast': " + str(casts) + '}'
                # elif len(crews) > 0:
                #     _meta['credits'] = "{'crew': " + str(crews) + '}'

            # if 'trailers' in meta and meta['trailers']:
            #     if 'youtube' in meta['trailers']:
            #         trailers = ''
            #         for t in meta['trailers']['youtube']:
            #             if t['type'] == 'Trailer':
            #                 trailers = self.URL_TRAILER % t['source']
            #         if trailers:
            #             _meta['trailer'] = trailers
            # elif 'videos' in meta and meta['videos']:
            #     if 'results' in meta['videos']:
            #         trailers = ''
            #         for t in meta['videos']['results']:
            #             if t['type'] == 'Trailer' and t['site'] == 'YouTube':
            #                 trailers = self.URL_TRAILER % t['key']
            #         if trailers:
            #             _meta['trailer'] = trailers

            if 'number_of_seasons' in meta and meta['number_of_seasons']:
                _meta['number_of_seasons'] = meta['number_of_seasons']

            if 'alternative_titles' in meta and meta['alternative_titles']:
                titles = 'titles' if _meta['mediatype'] == 'movie' else 'results'
                strtitles = str(meta['alternative_titles'])
                listAliases = eval(strtitles)
                origin_country = str(meta['origin_country'][0]) if 'origin_country' in meta else ''
                if len(listAliases[titles]) > 0:
                    lialiases = listAliases[titles]
                    # aliases = [i['title'] for i in lialiases if i['iso_3166_1'] in ['DE', 'US', 'EN', 'AT', 'CN', origin_country]]
                    aliases = [i['title'] for i in lialiases if i['iso_3166_1'] in ['DE', 'US', 'EN', 'AT', origin_country]]
                    _meta['aliases'] = aliases

            return _meta
        except Exception as e:
            print(e)
            pass
