# Local Listen

A script to find a few popular songs (on [Google Play (All Access)](http://music.google.com)) of the bands that are performing nearby within the next week (found using [JamBase](http://jambase.com)).  It adds the songs to a playlist on Google Play so you can listen and discover shows you wouldn't want to miss.

To use this script you need to have:
  
  1. Credentials to login to an "All Access" Google Play subscription
  2. An API key for JamBase, which you can sign up for at
     http://developer.jambase.com/page

This script depends on the following Python libraries:
  
    gmusicapi requests gitpass

To use it, install these dependencies.  Then edit the parameters at the top of the script (e.g. `zipcode`, `name_of_playlist`).  Then run the script (`python locallisten.py`). 

The first time you run the script it will ask you to type in your Google Play password and your JamBase API key.  `gitpass` saves these as hidden files so you don't have to type them in again.

Dustin Smith  
dustin@media.mit.edu

2014/4/23
