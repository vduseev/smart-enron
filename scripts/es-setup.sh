#!/bin/bash

DOMAIN="smart-enron"
ES_VERSION=5.5
INSTANCE_COUNT=2
VOLUME_SIZE=10
IAM_ARN="arn:aws:iam::610780818249:root"
RES_ARN="arn:aws:es:us-east-1:610780818249:domain/"$DOMAIN"/*"


aws es create-elasticsearch-domain \
    --domain-name $DOMAIN \
    --elasticsearch-version $ES_VERSION \
    --elasticsearch-cluster-config \
        InstanceType=m2.small.elasticsearch,InstanceCount=$INSTANCE_COUNT \
    --ebs-options \
        EBSEnabled=true,VolumeType=standard,VolumeSize=$VOLUME_SIZE

aws es update-elasticsearch-domain-config \
    --domain-name $DOMAIN \
    --access-policies \
        '{
          "Version": "2012-10-17",
          "Statement": [
            {
              "Effect": "Allow",
              "Principal": {
                "AWS":' $IAM_ARN '
              },
              "Action": "es:*",
              "Resource":' $RES_ARN '
            }
          ]
        }'