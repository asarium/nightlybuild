#!/bin/env python3

import argparse
import os
import sys
from itertools import groupby

import semantic_version
import yaml

import github
import installer
import nebula
from forum import ForumAPI, FileGroup
from script_state import ScriptState

abspath = os.path.abspath(__file__)
dname = os.path.dirname(abspath)
os.chdir(dname)

parser = argparse.ArgumentParser()
parser.add_argument("--config", help="Sets the config file", default="config.yml")
parser.add_argument("version", help="The version to mark this release as")
parser.add_argument("tag_name", help="Overrides the tag name to check. This skips the tag and push phase of the script",
                    default=None, nargs='?')

args = parser.parse_args()

config = {}

with open(args.config, "r") as f:
    try:
        config = yaml.load(f)
    except yaml.YAMLError as e:
        print(e)
        sys.exit(1)


class ReleaseState(ScriptState):
    def __init__(self, version):
        super().__init__(config)
        self.version = version

    def post_build_actions(self):
        if not self.success:
            print("A release build failed to compile!")
            return False

        # Get the file list
        files, sources = github.get_release_files(self.tag_name, config)

        print("Generating installer manifests")
        for file in files:
            installer.get_file_list(file)

        # Construct the file groups
        groups = dict(((x[0], FileGroup(x[0], list(x[1]))) for x in groupby(files, lambda g: g.group)))

        print(installer.render_installer_config(self.version, groups, self.config))

        nebula.submit_release(
            nebula.render_nebula_release(self.version, "rc" if self.version.prerelease else "stable", files),
            config['nebula']['user'], config['nebula']['password'])

        date = self.date.strftime(ScriptState.DATEFORMAT_FORUM)

        forum = ForumAPI(self.config)
        forum.post_release(date, self.version, groups, sources)
        return True

    def get_tag_name(self, params):
        base = "release_{}_{}_{}".format(self.version.major, self.version.minor, self.version.patch)

        if len(self.version.prerelease) > 0:
            base += "_" + "_".join(self.version.prerelease)

        return base

    def get_tag_pattern(self):
        return "release_*"

    def do_replacements(self, date, current_commit):
        with open(os.path.join(self.config["git"]["repo"], "version_override.cmake"), "a") as test:
            test.write("set(FSO_VERSION_MAJOR {})\n".format(self.version.major))
            test.write("set(FSO_VERSION_MINOR {})\n".format(self.version.minor))
            test.write("set(FSO_VERSION_BUILD {})\n".format(self.version.patch))
            test.write("set(FSO_VERSION_REVISION 0)\n")
            test.write("set(FSO_VERSION_REVISION_STR {})\n".format("-".join(self.version.prerelease)))


def main():
    script_state = ScriptState.load_from_file()

    if not semantic_version.validate(args.version):
        print("Specified version is not a valid version string!")
        return

    version = semantic_version.Version(args.version)
    if script_state is None:
        # An existing script state overrides the commandline argument
        if args.tag_name is not None:
            script_state = ReleaseState(version)
            script_state.state = ScriptState.STATE_TAG_PUSHED
            script_state.tag_name = args.tag_name
        else:
            if script_state is None:
                script_state = ReleaseState(version)
    else:
        if args.tag_name:
            print("Tag name ignored because there was a stored script state.")

        if not isinstance(script_state, ReleaseState):
            print("State object is not a nightly state! Delete 'state.pickle' or execute right script.")
            return

    # Always use the loaded values to allow changing the config while a script has a serialized state on disk
    script_state.config = config
    script_state.execute()


if __name__ == "__main__":
    main()
