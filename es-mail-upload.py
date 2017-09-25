import os
import argparse
import configparser
from email.parser import Parser
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from pathlib import Path
import json


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


def index_email_obj(es, email):
    es.index(
        index="emails",
        doc_type="email",
        body=email
    )


def upload_messages(es, path):

    # Initialize email parser
    email_parser = Parser()

    PREFIX_TRIM_AMOUNT = len(path) + 1

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
        if mailbox_owner != 'allen-p':
            continue

        # Extract mail folder name
        mail_folder = os.path.join(parts[1], *parts[2:])
        # if mail_folder != 'straw':
        #     continue

        print('The data:')
        print('  root:', root)
        print('  owner:', mailbox_owner)
        print('  folder:', mail_folder)
        print('  messages:')

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
                for key, value in msg.items():
                    email['headers'][key] = value


                # index_email_obj(es, email)
                print(json.dumps(email, indent=True))


if __name__ == "__main__":

    # Parse arguments
    args = parse_arguments()

    # Parse config
    conf = parse_config(args.config_path)

    # Connect to ElasticSearch
    # es = es_connect(
    #     conf.aws_access_key,
    #     conf.aws_secret_key,
    #     conf.region,
    #     conf.host
    # )
    #
    # print(es.cluster.health())

    upload_messages(None, conf.enron_path)
