picsort
=======

# installation

If you've cloned this repository run:

    python setup.py install

If you'd like to use PyPi:

    pip install picsort

# background

This is a script that I wrote because I had thousands of raw images on my computer
that needed to be sorted and imported into Lightroom.  Instead of manually checking
for duplicates, I decided to make a computer do the work for me.

As implemented, this program is invoked using:

    python sort.py -o output_directory ~/Pictures

This will find all pictures in my <code>~/Pictures</code> directory.  For each picture
found, the program will compute its sha1 checksum to include in the output filename.
The program will also use Exif information to determine the camera model and when the
picture was taken, according to exif data.

With this information, the program will copy the image file into a path like this:

    /Users/jhford/output_directory/NIKON D7000/2014/6/6/DSC_1111_sha1_abcd1234.NEF

By computing the sha1 checksum, we can ignore duplicates of each source image and only
have a single copy of each file in the output directory.  Sha1 checksums are a way to
uniquely identify a file with 40 characters.

I try to find all sidecar files for each copy of the raw image.  If I only find one,
it's added to the output directory.  If more than one sidecar is found, I take the
one with the most recent modified time and suffix the remainders with sidecarN.

If you want to verify your store of photos, you can use the verify mode by doing this:

    python sort.py --verify output_directory

This will tell you which files failed to be verified.

Both sorting and verifying files will create file in the directory where the script
was started called <code>failed_files.json</code>.  The format of this file will be
appropriate for the operation being conducted.
