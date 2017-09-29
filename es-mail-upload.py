import json
import argparse
import configparser
from datetime import datetime
from elasticsearch_api import ElasticSearchAPI, BulkGenerator
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

    # Read Elastic Search index parameters
    index_config = config['ES']['INDEX_CONFIG']
    bulk_index_def = config['ES']['BULK_INDEX_DEFINITION']
    config['ES']['BULK_SIZE'] = int(config['ES']['BULK_SIZE'])
    # Parse JSON config values
    config['ES']['INDEX_CONFIG'] = json.loads(index_config)
    config['ES']['BULK_INDEX_DEFINITION'] = json.loads(bulk_index_def)

    return config


if __name__ == "__main__":

    # Parse arguments
    args = parse_arguments()

    # Parse config
    conf = parse_config(args.config_path)

    # Connect to ElasticSearch
    api = ElasticSearchAPI()
    api.timeout = conf['ES']['TIMEOUT']
    api.connect(
        conf['AWS']['AWS_ACCESS_KEY'],
        conf['AWS']['AWS_SECRET_KEY'],
        conf['AWS']['REGION'],
        conf['AWS']['HOST']
    )

    print("Cluster health:")
    print(json.dumps(api.get_cluster_health(), indent=True))

    api.create_index(conf['ES']['INDEX_NAME'], conf['ES']['INDEX_CONFIG'])
    print('Index "emails" is created')

    api.set_refresh_rate(
        conf['ES']['INDEX_NAME'],
        ElasticSearchAPI.NO_REFRESH
    )
    print("Refresh settings are updated")

    print('Started uploading...', datetime.now())
    email_parser = EmailParser(email_file_encoding=conf['ENRON']['ENCODING'])
    bulk_generator = BulkGenerator(
        bulk_index_definition=conf['ES']['BULK_INDEX_DEFINITION'],
        bulk_size=conf['ES']['BULK_SIZE'],
        item_generator=email_parser.walk(args.dataset_path)
    )

    for bulk in bulk_generator.generate():
        resp = api.upload_bulk(bulk)
        print(bulk.size, 'emails uploaded.', 'Errors:', resp['errors'])
    print('Finished uploading...', datetime.now())

    api.set_refresh_rate(
        conf['ES']['INDEX_NAME'],
        ElasticSearchAPI.STANDARD_REFRESH
    )
    print("Refresh settings are set back")

    print("Forced merge started...")
    api.force_merge(index_name=conf['ES']['INDEX_NAME'])
    print("Forced merge finished")
