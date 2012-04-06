#!/usr/bin/env python

"""illustrates using http upload to send a file in clear text to a configured server
    uploads this file to my server (which saves then deletes the file)
    NOTE: files are sent "as is"; you have to encrypt beforehand if desired
"""
__author__ = 'Jeremy R. Gray'

from psychopy.contrib.http import post

# edit info to reflect your set-up:
info = {
    'host': 'scanlab.psych.yale.edu', # your server; IP address is fine
    'selector': 'http://scanlab.psych.yale.edu/upload_test/up_no_save.php',
    #'selector': 'http://your_server_here/your_path_here/up.php',
    'filename': __file__} # path to file to upload (__file__ is this script--it will upload itself)

print 'trying %s:' % info['selector']
status = post.upload(**info) # do the upload, get return value
print status

if not status.startswith('success'): # handle your error conditions, e.g., warn that upload failed
    print '''\nFAILED.\na good upload will return something like this (different sha256 and byte count):
success good_upload c5df3bf286b8e3cc9bfccaf1218adf43342b6725c901987bda7989e29c136b45 854'''