import os
import vlc
import time
import glob
import boto3
import argparse

import json

import numpy as np
import random

from python_telnet_vlc import VLCTelnet

partying = True
VIDEO_DIR = None
video_dict = {}
VIDEO_TIME = 9.8
video_plays = {} # map filename to num plays

def softmax(x):
    z = x - max(x)
    numerator = np.exp(z)
    denominator = np.sum(numerator)
    softmax = numerator/denominator
    return softmax

class VLCPlayer:
    def __init__(self):
        self.playlist = VLCTelnet("localhost", "secret", 9999) # set accordingly...
        self.video_list = []
        self.playing = False
        self.vid_start_time = None
        self.clip_time = VIDEO_TIME # total time for a single clip, clips must be same length
        self.clip_playing = False
        self.next_clip = None

        # Playlist settings
        #self.playlist.loop()
        self.playlist.set_volume(0)
        self.playlist.clear()
        #self.playlist.random()
 
    def add_video(self, video):
        self.playlist.add(video.abspath)
        self.video_list.append(video)
        self.video_list[-1].vlc_index = len(self.video_list)
        print(f"[Add to playlist] {video.filename}")

    def play(self):
        if not self.playing:
            self.vid_start_time = time.time()
            self.playing = True
        total_play_time = time.time() - self.vid_start_time 
        clip_clock = total_play_time % VIDEO_TIME

        if clip_clock <= 0.1 and self.clip_playing == False:
            self.clip_playing == True
            if self.next_clip:
                self.next_clip.plays += 1
                self.playlist.clear()
                self.playlist.add(self.next_clip.abspath)
                self.playlist.play()
                print(f"[Play clip] [p(x)={self.next_clip.p}%] {self.next_clip.filename}")
                video_plays[self.next_clip.filename] = video_plays.get(self.next_clip.filename, 0) + 1
                #self.playlist.play()
            self.next_clip = self.smart_shuffle_choose_next(video_dict)
        if clip_clock >= VIDEO_TIME - 0.1:
            self.clip_playing = False

    def smart_shuffle_choose_next(self, video_dict):
        num_clips = len(self.video_list)
        x = np.zeros(num_clips)
        for i in range(num_clips):
            video = self.video_list[i]
            x[i] = video.plays
        p = softmax(-x)

        # TODO save video_plays dict

        index = np.random.choice(np.arange(0, num_clips), p=p)
        self.video_list[index].p = int(p[index]*100)

        return self.video_list[index]


class Video:
    def __init__(self, filename):
        self.filename = filename
        self.remote_filesize = -1
        self.local_filesize = -1
        self.abspath = os.path.abspath(os.path.join(VIDEO_DIR, filename))
        self.premiered = False # Flag to check if video has been shown yet
        self.plays = 0
        self.vlc_index = -1

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

def load_video_plays():
    # TODO read num_plays.json
    pass

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
                time.sleep()

        s3 = boto3.Session().resource('s3')
        
        if args.list:
            list_buckets(s3)
            return

        
        check_bucket_exists(args.bucket, s3)
        bucket = s3.Bucket(args.bucket)

        # Loop videos & check bucket for updates in online mode
        start_time = time.time()
        initialized = False
        while partying:
            if (time.time() - start_time) % VIDEO_TIME >= VIDEO_TIME-0.1:
                print(f"[Ping s3] {len(video_dict.keys())} videos so far")
                check_for_updates(bucket, vlc_player)
                if not initialized:
                    time.sleep(VIDEO_TIME / 2) # check s3 in middle of a clip
                initialized = True
            if initialized:
                vlc_player.play()
            time.sleep(0.1)
    except:
        raise Exception("Something went wrong with wb3 :(")

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