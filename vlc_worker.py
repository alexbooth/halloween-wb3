import os
import vlc
import time
import glob
import boto3
import argparse

import random

from python_telnet_vlc import VLCTelnet

partying = True
VIDEO_DIR = None
video_dict = {}


class VLCPlayer:
    def __init__(self):
        self.playlist = VLCTelnet("localhost", "secret", 9100) # set accordingly...
        self.video_list = []

        # Playlist settings
        self.playlist.loop()
        self.playlist.set_volume(0)
        #self.playlist.fullscreen()
        self.playlist.clear()

    def add_video(self, video):
        self.playlist.add(video.abspath)
        print(f"[Add to playlist] {video.filename}")

        self.video_list = list(video_dict.keys())
        random.shuffle(self.video_list)

        self.playlist.clear()
        for filename in self.video_list:
            print("adding ", video_dict[filename].abspath)
            self.playlist.add(video_dict[filename].abspath)

        # Clear the playlist /
        # Randomize video order /
        # Prefix all unpremiered videos to the front :(
        # Add everything to the playlist again /

    def play(self):
        self.playlist.play()

class Video:
    def __init__(self, filename):
        self.filename = filename
        self.remote_filesize = -1
        self.local_filesize = -1
        self.abspath = os.path.abspath(os.path.join(VIDEO_DIR, filename))
        self.premiered = False # Flag to check if video has been shown yet

    def __str__(self):
        return self.filename

def init_s3_resource():
    try:
        print("Initializing connection to s3 resource")
        return boto3.Session().resource('s3')
    except:
        raise Exception("Error connecting to s3")

def list_files(bucket):
    for i, obj in enumerate(bucket.objects.all()):
        filename = obj.key
        filesize = read_filesize_from_s3(bucket, filename)
        print(f"[File {i}] [{filesize} bytes] {filename}")

def list_buckets(s3):
    try:
        print("Listing buckets...")
        for bucket in s3.buckets.all():
            print(bucket.name)
            list_files(bucket)
    except:
        print("Error: Connection issue")

def init_video(bucket, obj):
    filename = obj.key
    abspath = os.path.join(VIDEO_DIR, filename)

    remote_filesize = read_filesize_from_s3(bucket, filename)
    local_filesize = read_filesize_from_disk(abspath)

    if remote_filesize != local_filesize:
        print(f"[Dowload from bucket] {filename}")
        bucket.download_file(filename, abspath)
        local_filesize = read_filesize_from_disk(abspath)
    if remote_filesize != local_filesize:
        raise Exception("something is wrong...very wrong...")

    return Video(filename)

def check_for_updates(bucket, vlc_player):
    try:
        for obj in bucket.objects.all():
            if obj.key not in video_dict.keys():
                video_dict[obj.key] = init_video(bucket, obj)
                vlc_player.add_video(video_dict[obj.key])
    except:
        raise Exception()
        print("Error: Connection issue")


def read_filesize_from_s3(bucket, filename):
    return bucket.Object(filename).content_length

def read_filesize_from_disk(abspath):
    if os.path.isfile(abspath):
        return os.path.getsize(abspath)
    else:
        return -1

def check_bucket_exists(bucket, s3):
    try:
        if args.bucket not in {x.name for x in s3.buckets.all()}:
            raise Exception(f"Invalid bucket name was given (name='{args.bucket}')")
    except:
        print("Error: Connection issue")

def init_videos_offline(vlc_player):
    files = glob.glob(os.path.join(VIDEO_DIR, "*.mp4"))

    for abspath in files:
        filename = os.path.basename(abspath)
        video_dict[filename] = Video(filename)
        vlc_player.add_video(video_dict[filename])

    print(f"Added {len(files)} videos to playlist")

def main(args):
    try:
        if not args.dir and not args.list:
            raise Exception("Local video storage directory not specified")

        vlc_player = VLCPlayer()

        # Loop videos in offline mode
        if args.offline:
            print("Continuing in offline mode...")
            init_videos_offline(vlc_player)
            while partying:
                vlc_player.play()
                time.sleep(10)

        s3 = boto3.Session().resource('s3')
        
        if args.list:
            list_buckets(s3)
            return

        
        check_bucket_exists(args.bucket, s3)
        bucket = s3.Bucket(args.bucket)

        # Loop videos & check bucket for updates in online mode
        while partying:
            print(f"Pinging s3... {len(video_dict.keys())} videos so far")
            check_for_updates(bucket, vlc_player)
            vlc_player.play()
            time.sleep(10)
    except:
        raise Exception("Something went wrong with workerbae3 :(")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-l', '--list', dest='list', action="store_true", help='List buckets and files')
    parser.add_argument('-b', '--bucket', dest='bucket', action='store', type=str, help='Bucket to download from')
    parser.add_argument('-d', '--dir', dest='dir', action='store', type=str, help='Local video storage dir')
    parser.add_argument('-o', '--offline', dest='offline', action="store_true", help='Start in offline mode')
    args = parser.parse_args()
    if args.dir:
        VIDEO_DIR = os.path.abspath(args.dir)
        os.makedirs(VIDEO_DIR, exist_ok=True)
    main(args)