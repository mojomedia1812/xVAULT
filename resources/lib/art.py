

#2021-04-22

import requests
from resources.lib.control import  getSetting, addonPoster, py2_encode

lang = 'de'

## TMDB
tm_api_key = getSetting('api.tmdb').strip()
tm_art_link = 'http://api.themoviedb.org/3/%s/%s/images?api_key=%s&language=en-US&include_image_language=%s,en,null' % ('%s', '%s', tm_api_key, lang)
tm_img_link = 'https://image.tmdb.org/t/p/%s%s'
poster_sizes = 'w500'

## fanart.tv
fanart_tv_api_key = getSetting('api.fanart.tv').strip()
fanart_tv_headers = {'api-key': fanart_tv_api_key}
fanart_tv_art_link = 'http://webservice.fanart.tv/v3/%s/%s'

addonPoster = addonPoster()

def _request(url, headers=''):
    if 'fanart' in url: headers = fanart_tv_headers
    else: headers = ''
    try:
        result = requests.get(url, headers=headers, timeout=5)
    except requests.exceptions.SSLError:
        try:
            result = requests.get(url, headers=headers, verify=False, timeout=5)
        except requests.RequestException:
            return None
    except requests.RequestException:
        return None
    return result if result.status_code == 200 else None


def _get_tmdb_poster(art, sizes):
    try:
        posterlist_tmdb = art['posters']
        posterlist_tmdb = [x for x in posterlist_tmdb if x.get('iso_639_1') == lang] \
                                  + [x for x in posterlist_tmdb if x.get('iso_639_1') == 'en'] \
                                  + [x for x in posterlist_tmdb if x.get('iso_639_1') not in [lang, 'en']]

        return tm_img_link % (sizes, posterlist_tmdb[0]['file_path'])
    except:
        return None


def _get_tmdb_art(mediaid,ID):
    url = tm_art_link % (mediaid, ID)
    art = (_request(url))
    if art:
        art = art.json()
        if 'posters' in art and len(art['posters']) >= 1: return _get_tmdb_poster(art, poster_sizes)
    return None


def _get_fanart_tv_poster(posterlist_fanarttv):
    try:
        posterlist_fanarttv_temp =  [x for x in posterlist_fanarttv if x.get('lang') == lang][::-1] \
                                           + [x for x in posterlist_fanarttv if x.get('lang') == 'en'][::-1] \
                                           + [x for x in posterlist_fanarttv if x.get('lang') in ['00', '']][::-1]

        if posterlist_fanarttv_temp == []:
            posterlist_fanarttv = [x for x in posterlist_fanarttv][::-1]
        else:
            posterlist_fanarttv = posterlist_fanarttv_temp
        if 'http' in str(posterlist_fanarttv[0]['url']):
            return py2_encode(posterlist_fanarttv[0]['url'])
        return None
    except:
        return None


def _get_fanart_art(mediaid, ID):
    url = fanart_tv_art_link % (mediaid, ID)
    art = _request(url)
    if art:
        art = art.json()
        if mediaid == 'movies':
            if 'movieposter' in art and len(art['movieposter']) >= 1: posterlist_fanarttv = art['movieposter']
            elif 'hdmovieclearart' in art and len(art['hdmovieclearart']) >= 1: posterlist_fanarttv = art['hdmovieclearart']
            elif 'moviethumb' in art and len(art['moviethumb']) >= 1: posterlist_fanarttv = art['moviethumb']
            elif 'hdmovielogo' in art and len(art['hdmovielogo']) >= 1: posterlist_fanarttv = art['hdmovielogo']
            else: return None
            return _get_fanart_tv_poster(posterlist_fanarttv)
        else:
            if 'tvposter' in art and len(art['tvposter']) >= 1: posterlist_fanarttv = art['tvposter']
            elif 'hdclearart' in art and len(art['hdclearart']) >= 1: posterlist_fanarttv = art['hdclearart']
            else: return None
            return _get_fanart_tv_poster(posterlist_fanarttv)
    return None


# Aquaman
# tt1477834 imdb    +fan    +themoviedb
# 297802    tmdb    +fan    +themoviedb

def getMovie_art(tmdb, imdb):
    #imdb = 'tt1477834' # test only
    poster = _get_tmdb_art('movie', imdb)
    #poster = None     # test only
    if poster:
        return poster
    else:
        poster = _get_fanart_art('movies', imdb)
        if poster: return poster
    return addonPoster


# the 100
# 'tt2661044' imdb   -themoviedb   -fan
# '48866'     tmdb   +themoviedb   -fan
# '268592'    tvdb   -themoviedb   +fan

def getTvShows_art(tmdb, tvdb): #tvdb
    #tmdb = '48866'
    poster = _get_tmdb_art('tv',tmdb)
    #poster = None
    if poster:
        return poster
    else:
        #tvdb = '268592'
        poster = _get_fanart_art('tv', tvdb)
        if poster: return poster
    return addonPoster

