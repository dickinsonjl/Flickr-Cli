# encoding: utf8
# !/usr/bin/env python
import logging
import os.path
import ntpath
import imghdr
import time
import magic


def valid_img(f):
    supported_file_mimes = ['image/jpeg', 'image/gif', 'image/png', 'video/quicktime']
    try:
        mg = magic.Magic(mime=True)
        mime_type = mg.from_file(f)
        if mime_type in supported_file_mimes:
            return True
    except Exception as e:
        print "Magic Exception"
        # magic not available etc.
    supported_types = ['jpeg', 'gif', 'png']
    try:
        file_type = imghdr.what(f)
        if file_type in supported_types:
            return True
    except AttributeError as e:
        # You probably passed something that is not a path.
        logging.warning(e)
    except IOError as e:
        # You passed a path that does not exist, or you do not have access to it.
        logging.warning(e)
    return False


def get_upload_size(files):
    return sum([os.path.getsize(f) for f in files])


class UploadedIndex(object):
    """Used to keep track of which files have been uploaded"""

    def __init__(self, directory):
        self.directory = directory
        self.uploadedFiles = []
        self.check_index()

    def check_index(self):
        if not os.path.exists(self.directory):
            print "directory bad!"
        elif not os.path.exists(os.path.join(self.directory, ".flickrCli")):
            print "no .flickrCli file found, will be created..."
        else:
            with open(os.path.join(self.directory, ".flickrCli"), "r") as f:
                for line in f:
                    full_path = os.path.join(self.directory, line.rstrip())
                    file_name = ntpath.basename(full_path)
                    if os.path.exists(full_path):
                        self.uploadedFiles.append(file_name)
                    else:
                        print "'%s' not found in directory. Will remove from index. " % full_path
                if len(self.uploadedFiles) > 0:
                    print "Skipping %s images already uploaded." % len(self.uploadedFiles)
            with open(os.path.join(self.directory, ".flickrCli"), 'w') as f:
                self.uploadedFiles = self.unique_list(self.uploadedFiles)
                for uploaded in self.uploadedFiles:
                    f.write('%s\n' % uploaded)

    def isfileindexed(self, file):
        file_name = ntpath.basename(file)
        if file_name in self.uploadedFiles:
            return True
        else:
            return False

    def fileuploaded(self, file):
        file_name = ntpath.basename(file)
        if file_name not in self.uploadedFiles:
            with open(os.path.join(self.directory, ".flickrCli"), 'a') as f:
                print "adding file to upload index: '%s'" % file_name
                f.write('%s\n' % file_name)

    def unique_list(self, seq):
        seen = set()
        seen_add = seen.add
        return [x for x in seq if not (x in seen or seen_add(x))]


class UploadStatus(object):
    """Used to maintain state while performing uploads."""
    # TODO: Is this actually being used?

    def __init__(self, file_list):
        if isinstance(file_list, basestring):
            # The file list is a directory and should be converted into a directory list.
            file_list = [os.path.join(file_list, f)
                         for f in os.listdir(file_list)
                         if not os.path.isdir(os.path.join(file_list, f))]

        self.file_list = file_list
        self.total_upload_size = get_upload_size(self.file_list)
        self._file_no = 0
        self.file = self.get_current_file()

    def increment(self):
        try:
            self._file_no += 1
            self.file = self.get_current_file()
            return self.file
        except IndexError:
            return None

    def get_current_file(self):
        return self.file_list[self._file_no]

    def uploaded_thus_far(self):
        return float(get_upload_size(
            self.file_list[0:self._file_no]))

    def status(self, progress):
        """
        Progress: Float: How much of the currently uploading file has been uploaded.
        """
        total = self.uploaded_thus_far() + float(progress * os.path.getsize(self.file)) / 100
        return round(total / self.total_upload_size * 100, 2)


class Photoset(object):
    """
    Object that helps organize photos into sets.

    Arguments
    flickr: A FlickrAPI object that grants access to your flickr API.
    """
    def __init__(self, flickr, pset):
        self.flickr = flickr
        self.photoset_id = ''
        self.photoset_name = pset

    def exists(self, title):
        """Returns Photoset ID that matches title, if such a set exists.  Otherwise false."""
        try:
            photosets = self.flickr.photosets_getList().find("photosets").findall("photoset")
        except:
            return False

        for p in photosets:
            if p.find("title").text == title:
                print "Found existing photoset '%s', id: %s" % (title, p.attrib["id"])
                return p.attrib["id"]
        return False

    def create(self, title):
        """Returns Photoset and returns ID."""
        photoset_id = self.flickr.photosets_create(
            method='flickr.photosets.create',
            title=title,
            primary_photo_id=self.primary_photo_id
        ).find("photoset").attrib['id']
        print "Created new photoset '%s', id: %s" % (title, photoset_id)
        # if we set the primary photo, we don't need to add the photo to the set
        self.photo_ids.remove(self.primary_photo_id)
        return photoset_id

    def get_photoset_id(self, title):
        self.photoset_id = self.exists(title) or self.create(title)

    def add_photos(self):
        """Adds photo ids to photoset on Flickr."""
        return [self.flickr.photosets_addPhoto(
            photoset_id=self.photoset_id,
            photo_id=i) for i in self.photo_ids]

    def add_single_photo(self, pid):
        """Adds one photo id to photoset on Flickr."""
        self.primary_photo_id = pid
        self.photo_ids = [pid]
        if self.photoset_id == '':
            self.get_photoset_id(self.photoset_name)
        # print "Adding photo id '%s' to photoset '%s' (id:%s)" % (pid, self.photoset_name, self.photoset_id)
        return self.add_photos()

    def __call__(self, title, ids, primary_photo_id=0):
        """Generates photoset based on information passed in call"""
        self.primary_photo_id = primary_photo_id or ids[0]
        self.photo_ids = ids
        self.get_photoset_id(title)
        if self.photo_ids:
            response = self.add_photos()
            return response


class AbstractDirectoryUpload(object):
    """
    Framework to create uploads to other locations.
    I was on an Object Oriented programming kick when I did this, don't judge me. orz
    """
    def __init__(self):
        self.files = []

    def filter_directory_contents(self, d, f):
        return os.path.isdir(os.path.join(d, f))

    def get_directory_contents(self, d):
        self.uIndex = UploadedIndex(d)
        self.files = [os.path.join(d, f)
                      for f in os.listdir(d)
                      if not self.filter_directory_contents(d, f)]

    def checkfileindex(self):
        new_files = []
        for f in self.files:
            if not self.uIndex.isfileindexed(f):
                new_files.append(f)
            else:
                pass
        self.files = new_files

    def prehook(self, **kwargs):
        pass

    def posthook(self, **kwargs):
        pass

    def upload(self):
        raise NotImplementedError

    def parse_response(self):
        raise NotImplementedError

    def __call__(self, directory, **kwargs):
        self.directory = directory

        self.prehook(**kwargs)
        self.get_directory_contents(self.directory)
        self.upload()
        self.parse_response()
        self.posthook(**kwargs)


class DirectoryFlickrUpload(AbstractDirectoryUpload):
    """
    Handles actual upload to Flickr.
    """
    def __init__(self, flickr):
        super(DirectoryFlickrUpload, self).__init__()
        self.ids = []
        self.tags = []
        self.photoset_name = ''
        self.responses = []
        self.failed_uploads = []
        self.flickr = flickr

    def filter_directory_contents(self, d, f):
        return not valid_img(os.path.join(d, f))

    def prehook(self, tags, pset, **kwargs):
        self.ids = []
        self.tags = ", ".join(tags)
        self.photoset_name = pset
        self.create_photoset = Photoset(self.flickr, pset)

    def flickr_upload(self, f, **kwargs):
        if not self.uIndex.isfileindexed(f):
            print "Uploading %s" % f
            try:
                f_response = self.flickr.upload(filename=f, tags=self.tags, is_public=kwargs.get('is_public', 0), is_family=kwargs.get('is_family', 0))
            except Exception:
                print "Failed to upload: %s" % f
                self.failed_uploads.append(f)
                time.sleep(10)
            else:
                # We will assume the file upload was successful for now. @TODO check attrib['stat']=="ok"
                self.uIndex.fileuploaded(f)
                photo_id = f_response.find("photoid").text
                if photo_id != '':
                    self.create_photoset.add_single_photo(photo_id)
                return f_response
        else:
            print "Skipping %s" % f
            return

    def upload(self):
        self.checkfileindex()
        print "Uploading %s images..." % len(self.files)
        self.responses = [(self.flickr_upload(f, is_public=0, is_family=0), f) for f in self.files]

    def parse_response(self):
        for (r, f) in self.responses:
            photo_id = r.find("photoid").text
            if str(photo_id) != '':
                if r.attrib['stat'] == "ok":
                    self.ids.append(photo_id)
                else:
                    self.failed_uploads.append(f)
        # self.ids = [r.find("photoid").text for (r, f) in self.responses if r.attrib['stat'] == "ok"]
        # self.failed_uploads = [f for (r, f) in self.responses if r.attrib['stat'] != "ok"]
        self.successful_uploads_count = len(self.ids)
        self.failed_uploads_count = len(self.failed_uploads)

    def posthook(self, **kwargs):
        self.handle_failed_uploads()
        print "Completed directory: %s" % self.directory

    def handle_failed_uploads(self):
        if len(self.failed_uploads) > 0:
            print "Failed to upload %s images." % len(self.failed_uploads)
            # TODO: retry failed uploads?


class PublicDirectoryUpload(DirectoryFlickrUpload):
    """Uploads files in a directory exclusively as "Public" files."""

    def flickr_upload(self, f, **kwargs):
        """dispatches upload command to flickr with appropriate details taken from the self object
        :type f: str
        The path to a file.
        """
        return super(PublicDirectoryUpload, self).flickr_upload(f, is_public=1, is_family=0)


class FamilyDirectoryUpload(DirectoryFlickrUpload):
    """Uploads files in a directory exclusively as "Family-only" files."""

    def flickr_upload(self, f, **kwargs):
        """dispatches upload command to flickr with appropriate details taken from the self object
        :type f: str
        The path to a file."""
        return super(FamilyDirectoryUpload, self).flickr_upload(f, is_public=0, is_family=1)
