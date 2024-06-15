import sys
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

from base64 import b32decode, b32encode
import json
from random import shuffle
import socket
from urllib.parse import parse_qs, quote, urlencode
from urllib.request import Request, urlopen


addonID = 'plugin.audio.radiobrowser'
addon = xbmcaddon.Addon(id=addonID)

base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
args = parse_qs(sys.argv[2][1:])

xbmcplugin.setContent(addon_handle, 'songs')

favourites = {}
profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
favourites_path = f'{profile}/favourites.json'


def get_radiobrowser_base_urls():
    """
    Get all base urls of all currently available radiobrowser servers

    Returns: 
    list: a list of strings

    """
    hosts = []
    # get all hosts from DNS
    ips = socket.getaddrinfo('all.api.radio-browser.info',
                             80, 0, 0, socket.IPPROTO_TCP)
    for ip_tuple in ips:
        ip = ip_tuple[4][0]

        # do a reverse lookup on every one of the ips to have a nice name for it
        host_addr = socket.gethostbyaddr(ip)

        # add the name to a list if not already in there
        if host_addr[0] not in hosts:
            hosts.append(host_addr[0])

    # sort list of names
    shuffle(hosts)
    # add "https://" in front to make it an url
    xbmc.log(f'Found hosts: {",".join(hosts)}')
    return list([f'https://{host}' for host in hosts])


def LANGUAGE(id):
    return addon.getLocalizedString(id).encode('utf-8')


def build_url(query):
    return f'{base_url}?{urlencode(query)}'


def add_link(stationuuid, name, url, favicon, bitrate):
    li = xbmcgui.ListItem(name)
    li.setProperty('IsPlayable', 'true')
    vinfo = li.getVideoInfoTag()
    vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
    # setSize not yet implemented in API, uncomment once they update kodi API
    # minfo = li.getMusicInfoTag()
    # minfo.setTitle(name)
    # minfo.setSize(bitrate)
    li.setInfo(type="Music", infoLabels={"Title": name, "Size": bitrate})
    local_url = build_url({'mode': 'play', 'stationuuid': stationuuid})

    if stationuuid in favourites:
        context_title = LANGUAGE(32009)
        context_url = build_url({
            'mode': 'del_station',
            'stationuuid': stationuuid})
    else:
        context_title = LANGUAGE(32010)
        context_url = build_url({
            'mode': 'add_station',
            'stationuuid': stationuuid,
            'name': name.encode('utf-8'),
            'url': url,
            'favicon': favicon,
            'bitrate': bitrate})

    li.addContextMenuItems([(context_title, f'RunPlugin({context_url})')])

    xbmcplugin.addDirectoryItem(
        handle=addon_handle,
        url=local_url,
        listitem=li,
        isFolder=False)


def download_file(uri, param):
    """
    Download file with the correct headers set

    Returns: 
    a string result

    """
    if param:
        uri = f'{uri}?{urlencode(param)}'
        xbmc.log(f'Request to {uri} Params: {",".join(param)}')
    else:
        xbmc.log(f'Request to {uri}')

    req = Request(uri)
    req.add_header('User-Agent', 'KodiRadioBrowser/1.4.0')
    req.add_header('Content-Type', 'application/json')
    with urlopen(req) as response:
        result = response.read()
    return result


def download_api_file(path, param):
    """
    Download file with relative url from a random api server.
    Retry with other api servers if failed.

    Returns: 
    a string result

    """
    servers = get_radiobrowser_base_urls()
    i = 0
    for server_base in servers:
        xbmc.log(f'Random server: {server_base} Try: {str(i)}')
        uri = server_base + path

        try:
            data = download_file(uri, param)
            return data
        except Exception as e:
            xbmc.log(f'Unable to download from api url: {uri}', xbmc.LOGERROR)
        i += 1
    return None


def add_playable_link(data):
    data_decoded = json.loads(data)
    for station in data_decoded:
        add_link(
            station['stationuuid'],
            station['name'],
            station['url'],
            station['favicon'],
            station['bitrate'])


def read_file(filepath):
    with open(filepath, 'r') as file:
        return json.load(file)


def write_file(filepath, data):
    with open(filepath, 'w') as file:
        return json.dump(data, file)


def add_to_favourites(stationuuid, name, url, favicon, bitrate):
    favourites[stationuuid] = {
        'stationuuid': stationuuid,
        'name': name,
        'url': url,
        'bitrate': bitrate,
        'favicon': favicon}
    write_file(favourites_path, favourites)


def del_from_favourites(stationuuid):
    if stationuuid in favourites:
        del favourites[stationuuid]
        write_file(favourites_path, favourites)
        xbmc.executebuiltin('Container.Refresh')


def mode_tags():
    data = download_api_file('/json/tags', None)
    data_decoded = json.loads(data)
    for element in data_decoded:
        tag_name = element['name']
        if int(element['stationcount']) > 1:
            try:
                local_url = build_url({
                    'mode': 'stations',
                    'key': 'tag',
                    'value': b32encode(tag_name.encode('utf-8'))})
                li = xbmcgui.ListItem(tag_name)
                vinfo = li.getVideoInfoTag()
                vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
                xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)
            except Exception as e:
                xbmc.err(e)

    xbmcplugin.endOfDirectory(addon_handle)


def mode_countries():
    data = download_api_file('/json/countries', None)
    data_decoded = json.loads(data)
    for element in data_decoded:
        country_name = element['name']
        if int(element['stationcount']) > 1:
            try:
                local_url = build_url({
                    'mode': 'states',
                    'country': b32encode(country_name.encode('utf-8'))})
                li = xbmcgui.ListItem(country_name)
                vinfo = li.getVideoInfoTag()
                vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
                xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)
            except Exception as e:
                xbmc.log("Station count is not of type int", xbmc.LOGERROR)

    xbmcplugin.endOfDirectory(addon_handle)


def mode_states():
    country = b32decode(args['country'][0])
    data = download_api_file(f"/json/states/{quote(country.decode('utf-8'))}/", None)
    data_decoded = json.loads(data)

    local_url = build_url({
        'mode': 'stations',
        'key': 'country',
        'value': b32encode(country)})
    li = xbmcgui.ListItem(LANGUAGE(32006))
    vinfo = li.getVideoInfoTag()
    vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)

    for element in data_decoded:
        state_name = element['name']
        if int(element['stationcount']) > 1:
            try:
                local_url = build_url({
                    'mode': 'stations',
                    'key': 'state',
                    'value': b32encode(state_name.encode('utf-8'))})
                li = xbmcgui.ListItem(state_name)
                vinfo = li.getVideoInfoTag()
                vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
                xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)
            except Exception as e:
                xbmc.log("Stationcount is not of type int", xbmc.LOGERROR)

    xbmcplugin.endOfDirectory(addon_handle)


def mode_stations():
    if 'url' in args:
        url = args['url'][0]
        param = None
    else:
        url = '/json/stations/search'
        key = args['key'][0]
        value = b32decode(args['value'][0])
        value = value.decode('utf-8')
        param = {key: value, 'order': 'clickcount', 'reverse': True}

    data = download_api_file(url, param)
    add_playable_link(data)

    xbmcplugin.endOfDirectory(addon_handle)

def mode_play():
    stationuuid = args['stationuuid'][0]
    data = download_api_file('/json/url/' + str(stationuuid), None)
    data_decoded = json.loads(data)
    uri = data_decoded['url']
    xbmcplugin.setResolvedUrl(addon_handle, True, xbmcgui.ListItem(path=uri))


def mode_search():
    dialog = xbmcgui.Dialog()
    search_string = dialog.input(LANGUAGE(32011), type=xbmcgui.INPUT_ALPHANUM)

    url = f'/json/stations/byname/{search_string}'
    data = download_api_file(url, None)
    add_playable_link(data)

    xbmcplugin.endOfDirectory(addon_handle)


def mode_favourites():
    for station in favourites.values():
        add_link(
            station['stationuuid'],
            station['name'],
            station['url'],
            station['favicon'],
            station['bitrate'])

    xbmcplugin.endOfDirectory(addon_handle)


def mode_add_station():
    favicon = args['favicon'][0] if 'favicon' in args else ''
    add_to_favourites(
        args['stationuuid'][0],
        args['name'][0],
        args['url'][0],
        favicon,
        args['bitrate'][0])

def mode_del_station():
    del_from_favourites(args['stationuuid'][0])


# create storage
if not xbmcvfs.exists(profile):
    xbmcvfs.mkdir(profile)

if xbmcvfs.exists(favourites_path):
    favourites = read_file(favourites_path)
else:
    write_file(favourites_path, favourites)

mode = args.get('mode', None)

if mode is None:
    local_url = build_url({'mode': 'stations', 'url': '/json/stations/topclick/100'})
    li = xbmcgui.ListItem(LANGUAGE(32000))
    vinfo = li.getVideoInfoTag()
    vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)

    local_url = build_url({'mode': 'stations', 'url': '/json/stations/topvote/100'})
    li = xbmcgui.ListItem(LANGUAGE(32001))
    vinfo = li.getVideoInfoTag()
    vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)

    local_url = build_url({'mode': 'stations', 'url': '/json/stations/lastchange/100'})
    li = xbmcgui.ListItem(LANGUAGE(32002))
    vinfo = li.getVideoInfoTag()
    vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)

    local_url = build_url({'mode': 'stations', 'url': '/json/stations/lastclick/100'})
    li = xbmcgui.ListItem(LANGUAGE(32003))
    vinfo = li.getVideoInfoTag()
    vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)

    local_url = build_url({'mode': 'tags'})
    li = xbmcgui.ListItem(LANGUAGE(32004))
    vinfo = li.getVideoInfoTag()
    vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)

    local_url = build_url({'mode': 'countries'})
    li = xbmcgui.ListItem(LANGUAGE(32005))
    vinfo = li.getVideoInfoTag()
    vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)

    local_url = build_url({'mode': 'search'})
    li = xbmcgui.ListItem(LANGUAGE(32007))
    vinfo = li.getVideoInfoTag()
    vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)

    local_url = build_url({'mode': 'favourites'})
    li = xbmcgui.ListItem(LANGUAGE(32008))
    vinfo = li.getVideoInfoTag()
    vinfo.addAvailableArtwork('DefaultFolder.png', 'icon')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=local_url, listitem=li, isFolder=True)

    xbmcplugin.endOfDirectory(addon_handle)

else:
    match mode[0]:
        case 'tags':
            mode_tags()
        case 'countries':
            mode_countries()
        case 'states':
            mode_states()
        case 'stations':
            mode_stations()
        case 'play':
            mode_play()
        case 'search':
            mode_search()
        case 'favourites':
            mode_favourites()
        case 'add_station':
            mode_add_station()
        case 'del_station':
            mode_del_station()
