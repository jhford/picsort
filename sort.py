import os
import optparse
import hashlib
import json
import shutil
from xml.dom import minidom
import multiprocessing
import Queue
import threading
import time

try:
    import exifread
except ImportError:
    print 'You are missing the exifread module.  Try installing it'
    print 'with "sudo pip install exifread" or "sudo easy_install exifread"'
    exit(1)


digest_type = 'sha1'
picture_extensions = ['.jpg', '.jpeg', '.psd', '.nef', '.cr2', '.png']

stdout_lock = threading.Lock()


def split_filename(filename):
    for e in picture_extensions:
        if filename.lower().endswith(e):
            ext = e
    basename = os.path.basename(filename)
    return os.path.dirname(filename), basename[:-len(e)], basename[-len(e):]


def find_pictures(root):
    img_files = []
    for root, dirs, files in os.walk(root):
        for f in sorted(files):
            dirname, basename, ext = split_filename(f)
            if ext.lower() in picture_extensions:
                img_files.append(os.path.abspath(os.path.join(root, f)))
    return img_files


def build_hashes(file_lists, num_threads, bufsize=1024*1024):
    directory = {}

    def update_directory(digest, new_file):
        with directory_lock:
            if directory.has_key(digest):
                directory[digest].append(new_file)
            else:
                directory[digest] = [new_file]

    def hash_file(filename):
        with open(filename) as f:
            h = hashlib.new(digest_type)
            while True:
                d = f.read(bufsize)
                if not d:
                    break
                h.update(d)
        return h.hexdigest()

    def worker():
        while True:
            item = q.get()
            if item is DONE:
                q.task_done()
                break
            digest = hash_file(item)
            update_directory(digest, item)
            q.task_done()

    if num_threads == 0:
        for l in file_lists:
            for f in l:
                digest = hash_file(f)
                update_directory(digest, f)
    else:
        directory_lock = threading.Lock()
        threads = []
        DONE = 'DONE'
        q = Queue.Queue()
        for i in range(num_threads):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.daemon = True
            t.start()

        for l in file_lists:
            for f in l:
                q.put(f)

        q.join()
        while len([x for x in threads if x.isAlive()]) != 0:
            q.put(DONE)
            for thread in threads:
                thread.join(0.001)

    return directory


def dirs_from_image_data(source):
    # http://www.sno.phy.queensu.ca/~phil/exiftool/TagNames/EXIF.html
    try:
        with open(source) as f:
            exifdata = exifread.process_file(f)
    except:
        return os.path.join('bad exif')
    dirs = []
    if exifdata.has_key('Image Model'):
        dirs.append(exifdata['Image Model'].printable)
    else:
        dirs.append('unknown camera')
    if exifdata.has_key('EXIF DateTimeOriginal'):
        date, time = exifdata['EXIF DateTimeOriginal'].printable.split(' ')
        year, month, day = date.split(':')
        dirs.extend([year, month, day])
    else:
        dirs.append('unknown date')
    return os.path.join(*dirs)
    

def find_sidecars(img_files):
    sidecars = []
    for img_file in img_files:
        dirname, basename, ext = split_filename(img_file)
        sidecar = os.path.join(dirname, basename + '.xmp')
        if os.path.exists(sidecar):
            sidecars.append(sidecar)
    return sidecars


def copy_file(source, dest):
    with stdout_lock:
        print 'Copying %s ==> %s' % (source, dest)
    dirname = os.path.dirname(dest)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    shutil.copy2(source, dest)


def alter_sidecars(source, dest, image_dest):
    with stdout_lock:
        print 'New sidecar for %s ==> %s' % (source, dest)
    dirname = os.path.dirname(dest)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    dom = minidom.parse(source)
    dom.getElementsByTagName('rdf:Description')[0].attributes.get('crs:RawFileName').value = image_dest
    with open(dest, 'w+') as f:
        f.write(dom.toxml())


def build_actions(new_root, directory):
    actions = []
    for digest in directory.keys():
        source = directory[digest][0]
        dirname, filename, ext = split_filename(source)

        data_based_directories = dirs_from_image_data(source)
        output_directory = os.path.join(new_root, data_based_directories)
        base_dest = '%s_%s_%s' % (filename, digest_type, digest)
        image_dest = base_dest + ext

        action = (copy_file, source, os.path.join(output_directory, image_dest))
        actions.append(action)

        sidecars = find_sidecars(directory[digest])
        if len(sidecars) == 0:
            continue

        default_sidecar_dest = os.path.join(output_directory, base_dest + '.xmp')
        newest_sidecar = max(sidecars, key=os.path.getctime)
        actions.append((alter_sidecars, newest_sidecar, default_sidecar_dest, image_dest))
        i = 1
        for sidecar in sidecars:
            if sidecar is newest_sidecar:
                continue
            sidecar_dest = os.path.join(output_directory, '%s_sidecar%d.xmp' %(base_dest, i))
            i += 1
            actions.append((alter_sidecars, sidecar, sidecar_dest, image_dest))
            
    return actions


def process_files(actions, num_threads):
    if num_threads == 0:
        for action in actions:
            action[0](*action[1:])
        return
    threads = []
    q = Queue.Queue()
    DONE='DONE'

    def worker():
        while True:
            item = q.get()
            if item is DONE:
                q.task_done()
                break
            item[0](*item[1:])
            q.task_done()

    for i in range(num_threads):
        t = threading.Thread(target=worker)
        threads.append(t)
        t.daemon = True
        t.start()

    for action in actions:
        q.put(action)

    q.join()
    while len([x for x in threads if x.isAlive()]) != 0:
        q.put(DONE)
        for thread in threads:
            thread.join(0.001)


def main():
    print 'Find and sort pictures'
    parser = optparse.OptionParser('%prog <dir1> <dirN>');
    parser.add_option('-o', '--output', help='Root directory for output',
                      action='store', dest='output', default=None)
    parser.add_option('-t', '--threads', help='Number of work threads to use.  0 means ignore threading',
                      action='store', dest='threads', default=multiprocessing.cpu_count())
    opts, args = parser.parse_args();

    try:
        threads = int(opts.threads)
    except ValueError:
        parser.error("Thread count must be an integer")
    
    if not opts.output:
        parser.error("You must specify an output directory")
    else:
        outputdir = os.path.abspath(opts.output)
        print "Output directory: %s" % outputdir
        
    if len(args) < 1:
        parser.error("You haven't specified any input directories")

    file_lists = []
    for arg in args:
        file_lists.append(find_pictures(arg))
    data = build_actions(outputdir, build_hashes(file_lists, threads))
    process_files(data, threads)
    print 'Done!'


if __name__ == '__main__':
    main()
