#!/bin/bash
# Retrieve a copy of terraform and aws.
# Make available on path.

curr_dir=$PWD
tf_version="$(cat .terraform_version)" || { echo "ERROR: .terraform_version file not found" >&2; exit 1; }
mkdir -p exec_bin
cd exec_bin

echo "pulling a terraform script."
if ! curl -o "terraform_${tf_version}_linux_amd64.zip" "https://releases.hashicorp.com/terraform/${tf_version}/terraform_${tf_version}_linux_amd64.zip" ; then
  echo "ERROR: coud not download terraform script" >&2
  exit 1
else
  unzip -u terraform_${tf_version}_linux_amd64.zip
  chmod a+x terraform
  rm terraform_${tf_version}_linux_amd64.zip
fi

export PATH=$PWD:$PATH
cd $curr_dir
