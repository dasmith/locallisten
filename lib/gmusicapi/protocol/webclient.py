# -*- coding: utf-8 -*-

"""Calls made by the web client."""

import base64
import copy
import hmac
import random
import string
import sys
from hashlib import sha1

import validictory

from gmusicapi.compat import json
from gmusicapi.exceptions import CallFailure, ValidationException
from gmusicapi.protocol.metadata import md_expectations
from gmusicapi.protocol.shared import Call, authtypes
from gmusicapi.utils import utils

base_url = 'https://play.google.com/music/'
service_url = base_url + 'services/'

#Shared response schemas, built to include metadata expectations.
song_schema = {
    "type": "object",
    "properties": dict(
        (name, expt.get_schema()) for
        name, expt in md_expectations.items()
    ),
    #don't allow metadata not in expectations
    "additionalProperties": False
}

song_array = {
    "type": "array",
    "items": song_schema
}

pl_schema = {
    "type": "object",
    "properties": {
        "continuation": {"type": "boolean"},
        "playlist": song_array,
        "playlistId": {"type": "string"},
        "unavailableTrackCount": {"type": "integer"},
        # unsure what this field does. sometimes it's not there.
        "token": {"type": "string", "required": False},
        #only appears when loading multiple playlists
        "title": {"type": "string", "required": False},
        "continuationToken": {"type": "string", "required": False},
    },
    "additionalProperties": False
}

pl_array = {
    "type": "array",
    "items": pl_schema
}


class Init(Call):
    """Called one time per session, immediately after login.

    This performs one-time setup:
    it gathers the cookies we need (specifically `xt`), and Google uses it
    to create the webclient DOM.

    Note the use of the HEAD verb. Google uses GET, but we don't need
    the large response containing Google's webui.
    """

    static_method = 'HEAD'
    static_url = base_url + 'listen'

    required_auth = authtypes(sso=True)

    #This call doesn't actually request/return anything useful aside from cookies.
    @staticmethod
    def parse_response(response):
        return response.text

    @classmethod
    def check_success(cls, response, msg):
        if response.status_code != 200:
            raise CallFailure(('status code %s != 200' % response.status_code), cls.__name__)
        if 'xt' not in response.cookies:
            raise CallFailure('did not receieve xt cookies', cls.__name__)


class WcCall(Call):
    """Abstract base for web client calls."""

    required_auth = authtypes(xt=True, sso=True)

    #validictory schema for the response
    _res_schema = utils.NotImplementedField

    @classmethod
    def validate(cls, response, msg):
        """Use validictory and a static schema (stored in cls._res_schema)."""
        try:
            return validictory.validate(msg, cls._res_schema)
        except ValueError as e:
            trace = sys.exc_info()[2]
            raise ValidationException(str(e)), None, trace

    @classmethod
    def check_success(cls, response, msg):
        #Failed responses always have a success=False key.
        #Some successful responses do not have a success=True key, however.
        #TODO remove utils.call_succeeded

        if 'success' in msg and not msg['success']:
            raise CallFailure(
                "the server reported failure. This is usually"
                " caused by bad arguments, but can also happen if requests"
                " are made too quickly (eg creating a playlist then"
                " modifying it before the server has created it)",
                cls.__name__)

    @classmethod
    def parse_response(cls, response):
        return cls._parse_json(response.text)


class AddToPlaylist(WcCall):
    """Adds songs to a playlist."""
    static_method = 'POST'
    static_url = service_url + 'addtoplaylist'

    _res_schema = {
        "type": "object",
        "properties": {
            "playlistId": {"type": "string"},
            "songIds": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "songId": {"type": "string"},
                        "playlistEntryId": {"type": "string"}
                    }
                }
            }
        },
        "additionalProperties": False
    }

    @staticmethod
    def dynamic_data(playlist_id, song_ids):
        """
        :param playlist_id: id of the playlist to add to.
        :param song_ids: a list of song ids
        """
        #TODO unsure what type means here. Likely involves uploaded vs store/free.
        song_refs = [{'id': sid, 'type': 1} for sid in song_ids]

        return {
            'json': json.dumps(
                {"playlistId": playlist_id, "songRefs": song_refs}
            )
        }

    @staticmethod
    def filter_response(msg):
        filtered = copy.copy(msg)
        filtered['songIds'] = ["<%s songs>" % len(filtered.get('songIds', []))]
        return filtered


class ChangePlaylistOrder(WcCall):
    """Reorder existing tracks in a playlist."""

    static_method = 'POST'
    static_url = service_url + 'changeplaylistorder'

    _res_schema = {
        "type": "object",
        "properties": {
            "afterEntryId": {"type": "string", "blank": True},
            "playlistId": {"type": "string"},
            "movedSongIds": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "additionalProperties": False
    }

    @staticmethod
    def dynamic_data(playlist_id, song_ids_moving, entry_ids_moving,
                     after_entry_id=None, before_entry_id=None):
        """
        :param playlist_id: id of the playlist getting reordered.
        :param song_ids_moving: a list of consecutive song ids. Matches entry_ids_moving.
        :param entry_ids_moving: a list of consecutive entry ids to move. Matches song_ids_moving.
        :param after_entry_id: the entry id to place these songs after. Default first position.
        :param before_entry_id: the entry id to place these songs before. Default last position.
        """

        # empty string means first/last position
        if after_entry_id is None:
            after_entry_id = ""
        if before_entry_id is None:
            before_entry_id = ""

        return {
            'json': json.dumps(
                {
                    "playlistId": playlist_id,
                    "movedSongIds": song_ids_moving,
                    "movedEntryIds": entry_ids_moving,
                    "afterEntryId": after_entry_id,
                    "beforeEntryId": before_entry_id
                }
            )
        }

    @staticmethod
    def filter_response(msg):
        filtered = copy.copy(msg)
        filtered['movedSongIds'] = ["<%s songs>" % len(filtered.get('movedSongIds', []))]
        return filtered


class DeletePlaylist(WcCall):
    """Delete a playlist."""

    static_method = 'POST'
    static_url = service_url + 'deleteplaylist'

    _res_schema = {
        "type": "object",
        "properties": {
            "deleteId": {"type": "string"}
        },
        "additionalProperties": False
    }

    @staticmethod
    def dynamic_data(playlist_id):
        """
        :param playlist_id: id of the playlist to delete.
        """
        return {
            'json': json.dumps(
                {"id": playlist_id}
            )
        }


class DeleteSongs(WcCall):
    """Delete a song from the entire library or a single playlist."""

    static_method = 'POST'
    static_url = service_url + 'deletesong'

    _res_schema = {
        "type": "object",
        "properties": {
            "listId": {"type": "string"},
            "deleteIds":
            {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "additionalProperties": False
    }

    @staticmethod
    def dynamic_data(song_ids, playlist_id='all', entry_ids=None):
        """
        :param song_ids: a list of song ids.
        :param playlist_id: playlist id to delete from, or 'all' for deleting from library.
        :param entry_ids: when deleting from playlists, corresponding list of entry ids.
        """

        if entry_ids is None:
            #this is strange, but apparently correct
            entry_ids = [''] * len(song_ids)

        return {
            'json': json.dumps(
                {"songIds": song_ids, "entryIds": entry_ids, "listId": playlist_id}
            )
        }

    @staticmethod
    def filter_response(msg):
        filtered = copy.copy(msg)
        filtered['deleteIds'] = ["<%s songs>" % len(filtered.get('deleteIds', []))]
        return filtered


class GetLibrarySongs(WcCall):
    """Loads tracks from the library.

    Libraries can have many tracks, so GM gives them back in chunks.

    Chunks will send a continuation token to get the next chunk.

    The first request needs no continuation token.
    The last response will not send a token.
    """

    static_method = 'POST'
    static_url = service_url + 'loadalltracks'

    _res_schema = {
        "type": "object",
        "properties": {
            "continuation": {"type": "boolean"},
            "differentialUpdate": {"type": "boolean"},
            "playlistId": {"type": "string"},
            "requestTime": {"type": "integer"},
            "playlist": song_array,
        },
        "additionalProperties": {
            "continuationToken": {"type": "string"}}
    }

    @staticmethod
    def dynamic_data(cont_token=None):
        """:param cont_token: (optional) token to get the next library chunk."""
        if not cont_token:
            req = {}
        else:
            req = {"continuationToken": cont_token}

        return {'json': json.dumps(req)}

    @staticmethod
    def filter_response(msg):
        """Only log the number of songs."""
        filtered = copy.copy(msg)
        filtered['playlist'] = ["<%s songs>" % len(filtered.get('playlist', []))]

        return filtered


class GetPlaylistSongs(WcCall):
    """Loads tracks from a playlist.
    Tracks include playlistEntryIds.
    """

    static_method = 'POST'
    static_url = service_url + 'loadplaylist'

    @classmethod
    def dynamic_data(cls, playlist_id):
        """
        :param playlist_id: id to retrieve from, or 'all' to get all playlists.
        """

        #This call has a dynamic response schema based on the request.
        # TODO wow, this is a terrible idea

        if playlist_id == 'all':
            cls._res_schema = {
                "type": "object",
                "properties": {
                    "playlists": pl_array,
                },
                "additionalProperties": False
            }

            return {'json': json.dumps({})}

        else:
            cls._res_schema = pl_schema
            return {'json': json.dumps({'id': playlist_id})}

    @staticmethod
    def filter_response(msg):
        """Log number of songs/playlists."""
        filtered = copy.copy(msg)

        if 'playlists' in msg:
            filtered['playlists'] = ["<%s playlists>" % len(filtered['playlists'])]

        else:
            filtered['playlist'] = ["<%s songs>" % len(filtered['playlist'])]

        return filtered


class ChangeSongMetadata(WcCall):
    """Edit the metadata of songs."""

    static_method = 'POST'
    static_url = service_url + 'modifyentries'

    _res_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "songs": song_array
        },
        "additionalProperties": False
    }

    @staticmethod
    def dynamic_data(songs):
        """
        :param songs: a list of dictionary representations of songs
        """
        return {'json': json.dumps({'entries': songs})}

    @staticmethod
    def filter_response(msg):
        filtered = copy.copy(msg)
        filtered['songs'] = ["<%s songs>" % len(filtered.get('songs', []))]
        return filtered

    @staticmethod
    def validate(response, msg):
        """The data that comes back doesn't follow normal metadata rules,
        and is meaningless anyway; it'll lie about results."""
        pass


class GetDownloadInfo(WcCall):
    """Get download links and counts for songs."""

    static_method = 'POST'
    static_url = service_url + 'multidownload'

    _res_schema = {
        "type": "object",
        "properties": {
            "downloadCounts": {
                "type": "object",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"}
                    }
                }
            },
            "url": {"type": "string"}
        },
        "additionalProperties": False
    }

    @staticmethod
    def dynamic_data(song_ids):
        """
        :param: (list) song_ids
        """
        return {'json': json.dumps({'songIds': song_ids})}


class GetStreamUrl(WcCall):
    """Used to request a streaming link of a track."""

    static_method = 'GET'
    static_url = base_url + 'play'  # note use of base_url, not service_url

    required_auth = authtypes(sso=True)  # no xt required

    _res_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "required": False},
            "urls": {"type": "array", "required": False},
            'now': {'type': 'integer', 'required': False},
            'tier': {'type': 'integer', 'required': False},
        },
        "additionalProperties": False
    }

    @staticmethod
    def dynamic_params(song_id):

        # https://github.com/simon-weber/Unofficial-Google-Music-API/issues/137
        # there are three cases when streaming:
        #   | track type              | guid songid? | slt/sig needed? |
        #    user-uploaded              yes            no
        #    AA track in library        yes            yes
        #    AA track not in library    no             yes

        # without the track['type'] field we can't tell between 1 and 2, but
        # include slt/sig anyway; the server ignores the extra params.
        key = '27f7313e-f75d-445a-ac99-56386a5fe879'
        salt = ''.join(random.choice(string.ascii_lowercase + string.digits) for x in range(12))
        sig = base64.urlsafe_b64encode(hmac.new(key, (song_id + salt), sha1).digest())[:-1]

        params = {
            'u': 0,
            'pt': 'e',
            'slt': salt,
            'sig': sig
        }

        # TODO match guid instead, should be more robust
        if song_id[0] == 'T':
            # all access
            params['mjck'] = song_id
        else:
            params['songid'] = song_id
        return params


class ReportBadSongMatch(WcCall):
    """Request to signal the uploader to reupload a matched track."""

    static_method = 'POST'
    static_url = service_url + 'fixsongmatch'
    static_params = {'format': 'jsarray'}

    #This no longer holds.
    expected_response = [[0], []]

    @classmethod
    def validate(cls, response, msg):
        pass
        #if msg != cls.expected_response:
        #    raise ValidationException("response != %r" % cls.expected_response)

    @staticmethod
    def dynamic_data(song_ids):
        return json.dumps([["", 1], [song_ids]])


class UploadImage(WcCall):
    """Upload an image for use as album art."""

    static_method = 'POST'
    static_url = service_url + 'imageupload'
    static_params = {'zx': '',  # ??
                     'u': 0}

    _res_schema = {
        'type': 'object',
        'properties': {
            'imageUrl': {'type': 'string', 'blank': False},
            'imageDisplayUrl': {'type': 'string', 'blank': False},
        },
        'additionalProperties': False
    }

    @staticmethod
    def dynamic_files(image_filepath):
        """
        :param image_filepath: path to an image
        """
        with open(image_filepath, 'rb') as f:
            contents = f.read()

        return {'albumArt': (image_filepath, contents)}


class GetSettings(WcCall):
    """Get data that populates the settings tab: labs and devices."""

    static_method = 'POST'
    static_url = service_url + 'loadsettings'

    _device_schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'date': {'type': 'integer',
                     'format': 'utc-millisec'},
            'id': {'type': 'string'},
            'name': {'type': 'string', 'blank': True},
            'type': {'type': 'string'},

            # only for type == PHONE:
            'model': {'type': 'string', 'blank': True, 'required': False},
            'manufacturer': {'type': 'string', 'blank': True, 'required': False},

            'carrier': {'type': 'string', 'blank': True, 'required': False},
        },
    }

    _lab_schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'description': {'type': 'string'},
            'enabled': {'type': 'boolean'},
            'name': {'type': 'string'},
            'title': {'type': 'string'},
        },
    }

    _res_schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'settings': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'devices': {'type': 'array', 'items': _device_schema},
                    'labs': {'type': 'array', 'items': _lab_schema},
                    'maxTracks': {'type': 'integer'},
                    'expirationMillis': {
                        'type': 'integer',
                        'format': 'utc-millisec',
                        'required': False,
                    },
                    'isSubscription': {'type': 'boolean', 'required': False},
                    'isTrial': {'type': 'boolean', 'required': False},
                    'hasFreeTrial': {'type': 'boolean', 'required': False},
                    'subscriptionNewsletter': {'type': 'boolean'},
                    'isCanceled': {'type': 'boolean', 'required': False},
                },
            },
        },
    }

    @staticmethod
    def dynamic_data(session_id):
        """
        :param: session_id
        """
        return {'json': json.dumps({'sessionId': session_id})}


class DeauthDevice(WcCall):
    """Deauthorize a device from GetSettings."""
    static_method = 'POST'
    static_url = service_url + 'modifysettings'

    @staticmethod
    def dynamic_data(device_id, session_id):
        return {'json': json.dumps({'deauth': device_id, 'sessionId': session_id})}

    @classmethod
    def validate(cls, response, msg):
        if msg.text != '{}':
            raise ValidationException("expected an empty object; received %r" % msg.text)
