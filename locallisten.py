#!/usr/bin/env python
""" 
LocalListen - https://github.com/dasmith/locallisten

The MIT License (MIT)

Copyright (c) 2014 Dustin Smith (dustin@media.mit.edu)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
#--------------------------------------------------------------------
# script parameters
zipcode = "02139"
radius_in_miles = "5"
name_of_playlist = "! Bands playing in Cambridge, MA"
#--------------------------------------------------------------------
import requests
import gitpass
from gmusicapi import Mobileclient

def get_and_clear_playlist(name_of_playlist):
    """ Returns the playlist after deleting its songs"""
    for play in gapi.get_all_user_playlist_contents():
        if play['name'] == name_of_playlist and not play['deleted']:
            pid= play['id']
            # delete the existing songs
            for track in play['tracks']:
                gapi.remove_entries_from_playlist(track['id'])
            return pid
    return gapi.create_playlist(name_of_playlist)


jambase_api_key = gitpass.gitpass("Enter your Jambase API key", "japi")

gapi = Mobileclient()
gapi.login(gitpass.gitpass("Enter your Google Play email", "gemail"),
           gitpass.gitpass("Enter your Google Play password", "gpass"))

playlist_id = get_and_clear_playlist(name_of_playlist)

data = {'zipCode': zipcode,
        'radius': radius_in_miles,
        'page': 0,
        'api_key': jambase_api_key}

response = requests.get("http://api.jambase.com/events", params=data)
data = response.json()

for event in data['Events']:
    for artist in event['Artists']:
        artist_name = artist['Name']
        print "\n", artist_name, "@", event['Venue']['Name'],
        
        # search Google All Access for the artist
        result = gapi.search_all_access(artist_name)
        
        # look at the first result
        for google_artist_data in result.get('artist_hits', []):
            google_artist = google_artist_data['artist']
            google_artist_id = google_artist['artistId']
            print "----> %s (%0.2f)" % (google_artist['name'], google_artist_data['score'])
            if google_artist_data['score'] > 200:
                # TODO: confirm high string similarity, as sometimes Google gives high scores to 
                # strange matches.
                song_data = gapi.get_artist_info(google_artist_id, include_albums=False, max_top_tracks=5, max_rel_artist=0)
                for top_track in song_data.get('topTracks', []):
                    #if top_track['genre'] in banned_genres:
                    #   continue 
                    print " + %s [%s]" % (top_track['title'], top_track['genre'])
                    song_id = top_track.get('id') or top_track.get('nid')
                    gapi.add_songs_to_playlist(playlist_id, song_id)
            break
