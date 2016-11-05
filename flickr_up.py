#!/usr/bin/python -u
# encoding: utf8
import sys
import os
from optparse import OptionParser
import webbrowser
import flickrapi
import flickr_cli
from ConfigParser import ConfigParser


def photoset_default_title(d):
    return os.path.basename(os.path.normpath(d))


def process_single_directory(d, ps, t):
    print d, t, ps

    config = ConfigParser()
    config.read('flickr.config')
    api_key = config.get('flickr', 'key')
    secret = config.get('flickr', 'secret')
    flickr = flickrapi.FlickrAPI(api_key, secret)

    if not flickr.token_valid(perms=u'write'):
        flickr.get_request_token(oauth_callback=u'oob')
        authorize_url = flickr.auth_url(perms=u'write')
        webbrowser.open_new_tab(authorize_url)
        verifier = unicode(raw_input('Verifier code: '))
        flickr.get_access_token(verifier)

    # upload = flickr_cli.DirectoryFlickrUpload(flickr)
    upload = flickr_cli.FamilyDirectoryUpload(flickr)
    upload(directory=d, pset=ps, tags=t)


parser = OptionParser(version="1.0")

parser.add_option("-d", "--directory", dest="directory",
                  help="The directory from which you wish to copy the files",
                  metavar="DIRECTORY")

parser.add_option("-e", "--extensive", dest="extensive",
                  help="The directory holding multiple sub-directories which will be unique photosets",
                  metavar="EXTENSIVE")

parser.add_option("-p", "--photoset",
                  dest="photoset", default=False,
                  help="the name for the photoset on flickr.")

parser.add_option("-t", "--tags",
                  action="append", dest="tags",
                  help="Tag to apply to pictures in this directory.")

parser.add_option("-q", "--quiet",
                  action="store_false", dest="verbose", default=True,
                  help="don't print status messages to stdout")

parser.add_option("-r", "--recursive",
                  action="store_false", dest="recursive", default=False,
                  help="recursively copy all subdirectories to different photosets")

parser.add_option("-R", "--RECURSIVE",
                  action="store_false", dest="same_recursive", default=False,
                  help="recursively copy all subdirectories to the same photoset. \
      Overrides -r.")

(options, args) = parser.parse_args()

if args:
    print "ERROR"
    print "Aborting due to unrecognized arguments:\n {}".format("\n\t".join(args))
    sys.exit(0)

if not options.directory:
    if not options.extensive:
        print "ERROR"
        print "You must pass a directory.\n (-d or -e /my/folder etc.)"
        sys.exit(0)

tags = options.tags or ""

if not options.tags:
    print "WARNING: You did not pass any tags.\n"

if options.extensive:
    extensive = options.extensive or "."
    print "Extensive mode."

    for dirpath, dirs, files in os.walk(extensive):
        for d in dirs:
            print 'dir:', d
            this_fullpath = os.path.abspath(dirpath) + '/' + d
            print 'fullpath:', this_fullpath
            photoset = photoset_default_title(this_fullpath)
            print "We will use the photoset title '{}'".format(photoset)
            process_single_directory(this_fullpath, photoset, tags)
else:
    directory = options.directory
    photoset = options.photoset or photoset_default_title(options.directory)

    if not options.photoset:
        print "WARNING: You did not pass a name for the photoset.\n"
        print "We will use the photoset title '{}'".format(photoset)
    process_single_directory(directory, photoset, tags)
