import json
import argparse
import configparser
from datetime import datetime
from elasticsearch_api import ElasticSearchAPI
from enron_email import EmailParser


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
    bulk_size = config['ELASTICSEARCH']['BULK_SIZE']
    timeout = config['ELASTICSEARCH']['TIMEOUT']
    # Parse JSON config values
    index_config = json.loads(index_config)
    bulk_index_def = json.loads(bulk_index_def)
    setattr(config, 'index_name', index_name)
    setattr(config, 'index_config', index_config)
    setattr(config, 'bulk_index_def', bulk_index_def)
    setattr(config, 'bulk_size', bulk_size)
    setattr(config, 'timeout', timeout)

    # Read dataset specific business rules
    email_encoding = config['ENRON']['ENCODING']
    setattr(config, 'email_encoding', email_encoding)

    return config


def pack_emails_into_bulks(path, encoding, bulk_index_def, bulk_size):
    parser = EmailParser(encoding)
    bulk_file = ''
    bulk_index_line = json.dumps(bulk_index_def)

    counter = 0
    for email in parser.walk(path):
        bulk_file += bulk_index_line + '\n'
        bulk_file += json.dumps(email) + '\n'
        counter += 1
        if counter % bulk_size == 0:
            yield bulk_file, counter
            bulk_file = ''

    # yield last portion
    if bulk_file:
        yield bulk_file, counter



if __name__ == "__main__":

    # Parse arguments
    args = parse_arguments()

    # Parse config
    conf = parse_config(args.config_path)

    # Connect to ElasticSearch
    api = ElasticSearchAPI()
    api.timeout = conf.timeout
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

    print('Started uploading...', datetime.now())
    for bulk in pack_emails_into_bulks(
        args.dataset_path,
        conf.email_encoding,
        conf.bulk_index_def,
        conf.bulk_size
    ):
        resp, amount = api.bulk(bulk)
        print(amount, 'emails uploaded.', 'Errors:', resp['errors'])
    print('Finished uploading...', datetime.now())

    api.set_index_refresh(conf.index_name, ElasticSearchAPI.STANDARD_REFRESH)
    print("Refresh settings are set back")

    print("Forced merge started...")
    api.force_merge(index_name=conf.index_name)
    print("Forced merge finished")
