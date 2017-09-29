from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth


class ElasticSearchAPI:
    NO_REFRESH = '-1'
    STANDARD_REFRESH = '1s'

    def __init__(self):
        self.region = ''
        self.host = ''
        self.http_auth = None
        self.es = None
        self.timeout = '60s'

    def connect(self, aws_access_key, aws_secret_key, region, host):
        self.http_auth = AWS4Auth(
            aws_access_key,
            aws_secret_key,
            region,
            'es'

        )

        self.es = Elasticsearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=self.http_auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )

    def create_index(self, index_name, index_config):
        self.es.indices.create(
            index=index_name,
            body=index_config
        )

    def set_refresh_rate(self, index_name, value):
        self.es.indices.put_settings(
            index=index_name,
            body=value
        )

    def force_merge(self, index_name, segments_count=5):
        self.es.indices.forcemerge(
            index=index_name,
            max_num_segments=segments_count
        )

    def get_cluster_health(self):
        return self.es.cluser.healt()

    def upload_bulk(self, bulk):
        return self.es.bulk(bulk.contents, self.timeout)
