import boto3
from botocore.client import Config
import argparse, os
 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-k', '--key', type=str, required=True, help="Space key")
    parser.add_argument('-s', '--secret', type=str, required=True, help="Space secret")
    parser.add_argument('-b', '--bucket', type=str, required=True, help="Bucket")
    parser.add_argument('-p', '--path', type=str, required=True, help="Upload path")
    parser.add_argument('-f', '--file', type=str, required=True, help="Source file")
    args = parser.parse_args()

    upload(args.key, args.secret, args.bucket, args.path, args.file)

def upload(key, secret, bucket, path, filename):
    print("Uploading '{}' to '{}'".format(filename, path))
    # Initialize a session using DigitalOcean Spaces.
    session = boto3.session.Session()
    client = session.client('s3',
                            region_name='nyc3',
                            endpoint_url='https://nyc3.digitaloceanspaces.com',
                            aws_access_key_id=key,
                            aws_secret_access_key=secret)

    client.upload_file(filename, bucket, path, ExtraArgs={'ACL':'public-read'})

if __name__ == "__main__":
    main()