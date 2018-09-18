

import re

import requests

from files import ReleaseFile
from util import retry_multi, GLOBAL_TIMEOUT


def get_file_list(tag_name, config):
    @retry_multi(5)
    def execute_request(path):
        headers = {
        }
        url = "https://bintray.com/api/v1" + path

        response = requests.get(url, headers=headers, timeout=GLOBAL_TIMEOUT)

        response.raise_for_status()

        return response.json()

    tag_regex = re.compile("nightly_(.*)")
    build_group_regex = re.compile("nightly_.*-builds-([^.]*).*")

    bintray_version = tag_regex.match(tag_name).group(1)

    path = "/packages/{subject}/{repo}/{package}/versions/{version}/files".format(**{
        "subject": config["bintray"]["subject"],
        "repo": config["bintray"]["repo"],
        "package": config["bintray"]["package"],
        "version": bintray_version,
    })

    files = execute_request(path)

    out_data = []
    for file in files:
        group_match = build_group_regex.match(file["path"]).group(1)
        download_url = "https://dl.bintray.com/{subject}/{repo}/{file_path}".format(**{
            "subject": config["bintray"]["subject"],
            "repo": file["repo"],
            "file_path": file["path"]
        })

        out_data.append(ReleaseFile(file["name"], download_url, group_match, file["sha1"]))

    return sorted(out_data, key=lambda x: x.group)
