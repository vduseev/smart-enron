import os
import argparse
import configparser
from email.parser import Parser
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from pathlib import Path
import json
import datetime


def parse_arguments():
    # Parse arguments
    parser = argparse.ArgumentParser(
        description='Upload Enron Dataset to ElasticSearch cluster'
    )
    parser.add_argument(
        '-c', '--config',
        dest='config_path',
        default='config.ini',
        help='path to config file'
    )

    arguments = parser.parse_args()
    return arguments


def parse_config(config_path):
    # Read config file
    config = configparser.ConfigParser()
    config.read(config_path)

    # Read Dataset properties
    enron_path = config['PATHS']['enron_dataset_path']
    setattr(config, 'enron_path', enron_path)

    # Read AWS properties
    aws_access_key = config['AWS']['AWS_ACCESS_KEY']
    aws_secret_key = config['AWS']['AWS_SECRET_KEY']
    region = config['AWS']['REGION']
    host = config['AWS']['HOST']
    setattr(config, 'aws_access_key', aws_access_key)
    setattr(config, 'aws_secret_key', aws_secret_key)
    setattr(config, 'region', region)
    setattr(config, 'host', host)

    return config


def es_connect(aws_access_key, aws_secret_key, region, host):
    aws_auth = AWS4Auth(aws_access_key, aws_secret_key, region, 'es')
    es = Elasticsearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=aws_auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )
    return es


def convert_date_to_es_format(date_string):
    # Example from email:
    # Thu, 2 Nov 2000 08:12:00 -0800 (PST)
    # Example from ES docs:
    # yyyy/MM/dd HH:mm:ss Z
    # First, cut off non standard time zone at the end
    date_string, _ = date_string.rsplit(' ', 1)
    date = datetime.datetime.strptime(
        date_string,
        '%a, %d %b %Y %H:%M:%S %z'
    )
    es_date = datetime.datetime.strftime(
        date,
        '%Y/%m/%d %H:%M:%S %z'
    )
    return es_date


def upload_messages(es, path):

    # Initialize email parser
    email_parser = Parser()

    PREFIX_TRIM_AMOUNT = len(path) + 1

    bulk_file = ''
    index_definition = {
        "index": {
            "_index": "emails",
            "_type": "email"
        }
    }
    bulk_index_line = json.dumps(index_definition)

    counter = 0
    mailbox_owner = 'no_owner'
    last_uploaded_count = 0
    for root, dirs, files in os.walk(path):
        user_directory = root[PREFIX_TRIM_AMOUNT:]

        # Split user_directory and sub directories into parts
        parts = Path(user_directory).parts

        # Ignore rows without sub folder
        # parts[0] is guaranteed to be a mailbox owner name
        # parts[1] exists when os.walk steps into user directory
        # and contains mail folders
        if len(parts) < 2:
            continue

        # Extract mailbox owner name
        mailbox_owner = parts[0]

        # Extract mail folder name
        mail_folder = os.path.join(parts[1], *parts[2:])

        # Index each email
        for file_name in files:
            file_path = os.path.join(root, file_name)

            with open(file_path, mode='r', encoding='cp1252') as msg_file:
                msg = email_parser.parse(msg_file)

                # Message Id will be generated automatically by ElasticSearch
                email = {}
                email['body'] = msg.get_payload()
                email['mail_folder'] = mail_folder
                email['mailbox_owner'] = mailbox_owner
                email['filename'] = file_name
                # Create headers dictionary and fill it with headers from file
                email['headers'] = {}

                try:
                    for key, value in msg.items():
                        # Convert date to standard ES format
                        if key == 'Date':
                            value = convert_date_to_es_format(value)

                        email['headers'][key] = value
                except ValueError:
                    continue

                bulk_file += bulk_index_line + '\n'
                bulk_file += json.dumps(email) + '\n'

                counter += 1

                if counter % 1000 == 0:
                    res = es.bulk(bulk_file, timeout='60s')
                    print('Errors:', res['errors'])
                    bulk_file = ''
                    print(
                        'Uploaded to', counter, 'items',
                        'to', mailbox_owner,
                        datetime.datetime.now()
                    )
                    last_uploaded_count = counter

    if counter != last_uploaded_count:
        res = es.bulk(bulk_file, timeout='60s')
        print('Errors:', res['errors'])
        print(
            'Uploaded to', counter, 'items',
            'to', mailbox_owner,
            datetime.datetime.now()
        )


if __name__ == "__main__":

    # Parse arguments
    args = parse_arguments()

    # Parse config
    conf = parse_config(args.config_path)

    # Connect to ElasticSearch
    es = es_connect(
        conf.aws_access_key,
        conf.aws_secret_key,
        conf.region,
        conf.host
    )

    print("Cluster health:")
    print(json.dumps(es.cluster.health(), indent=True))

    index_config = {
        "mappings": {
            "email": {
                "date_detection": True,
                "dynamic_date_formats": ["yyyy/MM/dd HH:mm:ss Z"]
            }
        }
    }

    es.indices.create(
        'emails',
        body=index_config
    )

    print('Index "emails" is created')

    no_refresh_settings = {
        "index": {
            "refresh_interval": "-1"
        }
    }

    es.indices.put_settings(
        body=no_refresh_settings,
        index='emails'
    )

    print("Refresh settings are updated")

    print('Starting uploading...', datetime.datetime.now())
    upload_messages(es, conf.enron_path)
    print('Finished uploading...', datetime.datetime.now())

    refresh_settings = {
        "index": {
            "refresh_interval": "1s"
        }
    }

    es.indices.put_settings(
        body=refresh_settings,
        index='emails'
    )

    print("Refresh settings are set back")

    print("Forced merge started...")
    es.indices.forcemerge(index='emails', max_num_segments=5)
    print("Forced merge finished")
