#!/bin/bash

sudo apt install unzip

# check if AWS is installed
if ! command -v aws &>/dev/null; then
    echo "Installing AWS CLI..."
    curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
    unzip awscliv2.zip
    sudo ./aws/install
fi

# configure aws (could be prompted)
export S3_ENDPOINT_URL=${S3_ENDPOINT_URL:-"https://usgs2.osn.mghpcc.org"}
aws configure

# download input data from S3
mkdir -p ~/landis/input ~/landis/output/

#landis input files
#aws s3 sync s3://landis-ii-input/interior-AK-input ~/landis/input --endpoint-url "$S3_ENDPOINT_URL"