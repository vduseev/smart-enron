import os
import json
import argparse
import configparser
from pathlib import Path
from datetime import datetime
from email.parser import Parser
from elasticsearch_api import ElasticSearchAPI


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
    parser.add_argument(
        '-d', '--dataset',
        dest='dataset_path',
        default='maildir',
        help='path to Enron email dataset dir'
    )

    arguments = parser.parse_args()
    return arguments


def parse_config(config_path):
    # Read config file
    config = configparser.ConfigParser()
    config.read(config_path)

    # Read AWS properties
    aws_access_key = config['AWS']['AWS_ACCESS_KEY']
    aws_secret_key = config['AWS']['AWS_SECRET_KEY']
    region = config['AWS']['REGION']
    host = config['AWS']['HOST']
    setattr(config, 'aws_access_key', aws_access_key)
    setattr(config, 'aws_secret_key', aws_secret_key)
    setattr(config, 'region', region)
    setattr(config, 'host', host)

    # Read Elastic Search index parameters
    index_name = config['ELASTICSEARCH']['INDEX_NAME']
    index_config = config['ELASTICSEARCH']['INDEX_CONFIG']
    bulk_index_def = config['ELASTICSEARCH']['BULK_INDEX_DEFINITION']
    bulk_count = config['ELASTICSEARCH']['BULK_COUNT']
    timeout = config['ELASTICSEARCH']['TIMEOUT']
    # Parse JSON config values
    index_config = json.loads(index_config)
    bulk_index_def = json.loads(bulk_index_def)
    setattr(config, 'index_name', index_name)
    setattr(config, 'index_config', index_config)
    setattr(config, 'bulk_index_def', bulk_index_def)
    setattr(config, 'bulk_count', bulk_count)
    setattr(config, 'timeout', timeout)

    # Read dataset specific business rules
    email_encoding = config['ENRON']['ENCODING']
    setattr(config, 'email_encoding', email_encoding)

    return config


def convert_date_to_es_format(date_string):
    # Example from email:
    # Thu, 2 Nov 2000 08:12:00 -0800 (PST)
    # Example from ES docs:
    # yyyy/MM/dd HH:mm:ss Z
    # First, cut off non standard time zone at the end
    date_string, _ = date_string.rsplit(' ', 1)
    date = datetime.strptime(
        date_string,
        '%a, %d %b %Y %H:%M:%S %z'
    )
    es_date = datetime.strftime(
        date,
        '%Y/%m/%d %H:%M:%S %z'
    )
    return es_date


def upload_messages(
        es,
        path,
        bulk_index_def,
        bulk_count,
        email_encoding,
        timeout
):

    # Initialize email parser
    email_parser = Parser()

    PREFIX_TRIM_AMOUNT = len(path) + 1

    bulk_file = ''
    bulk_index_line = json.dumps(bulk_index_def)

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

            with open(file_path, mode='r', encoding=email_encoding) as msg_file:
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

                if counter % bulk_count == 0:
                    res = es.bulk(bulk_file, timeout=timeout)
                    print('Errors:', res['errors'])
                    bulk_file = ''
                    print(
                        'Uploaded to', counter, 'items',
                        'to', mailbox_owner,
                        datetime.now()
                    )
                    last_uploaded_count = counter

    if counter != last_uploaded_count:
        res = es.bulk(bulk_file, timeout=timeout)
        print('Errors:', res['errors'])
        print(
            'Uploaded to', counter, 'items',
            'to', mailbox_owner,
            datetime.now()
        )


if __name__ == "__main__":

    # Parse arguments
    args = parse_arguments()

    # Parse config
    conf = parse_config(args.config_path)

    # Connect to ElasticSearch
    api = ElasticSearchAPI()
    api.connect(
        conf.aws_access_key,
        conf.aws_secret_key,
        conf.region,
        conf.host
    )

    print("Cluster health:")
    print(json.dumps(api.get_cluster_health(), indent=True))

    api.create_index(conf.index_name, conf.index_config)
    print('Index "emails" is created')

    api.set_index_refresh(conf.index_name, ElasticSearchAPI.NO_REFRESH)
    print("Refresh settings are updated")

    print('Starting uploading...', datetime.now())
    upload_messages(
        es=api.es,
        path=args.dataset_path,
        bulk_index_def=conf.bulk_index_def,
        bulk_count=conf.bulk_count,
        email_encoding=conf.email_encoding,
        timeout=conf.timeout
    )
    print('Finished uploading...', datetime.now())

    api.set_index_refresh(conf.index_name, ElasticSearchAPI.STANDARD_REFRESH)
    print("Refresh settings are set back")

    print("Forced merge started...")
    api.force_merge(index_name=conf.index_name)
    print("Forced merge finished")
