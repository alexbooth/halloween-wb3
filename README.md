# WorkerBee3

## Local setup

Install python packages

``` bash
pip3 install boto3 python-telnet-vlc
```

For Mac, install VLC 3.0.12, later versions will not work  

Configure AWS IAM credentials locally

``` bash
aws configure
```

***
Start VLC server

``` bash
vlc --extraintf telnet --telnet-password=secret --telnet-port=9999
```

Ensure password and port align within the script.

Start Wb3 service, and enjoy

``` bash
python3 vlc_worker.py -b my_bucket_name --dir my_video_storage_dir
```
