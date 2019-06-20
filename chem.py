#!/usr/bin/env python3.7

"""Multi environment manager

"""

import yaml
import json
import sys
import os
import argparse
import tempfile
import re

from subprocess import call
from collections import OrderedDict
from pprint import pprint


__author__ = "Stanislav Rudenko"
__version__ = 1.3
__doc__ = "Multi environment manager"


if sys.version_info < (3, 5, 0):
    sys.stderr.write("You need python 3.5 or later to run this script\n")
    sys.exit(1)


def load_config(spork_config_file):
    """
    fixme
    :return:
    """
    return yaml.load(open(spork_config_file).read())


def get_environment_groups(config):
    return config['environment_groups']


def attr_dict_new(attrs):
    """
    Example: default_attributes.client.ldap_server:final_value

    :param attrs: a dot tree string representation of a dict, see example above
    :return: dict from a dot string model
    """
    try:
        # path, value = attrs.split(':')
        path, value = attrs.split(':', 1)
        # path, value = re.split(r'(?<!\\):', attrs)
    except ValueError:
        path = attrs
        value = "undefined"

    def build(keys, item, array_build={}):
        """
        See examples here:
         http://stackoverflow.com/questions/12414821/checking-a-dictionary-using-a-dot-notation-string

        :param keys: a dot tree of an array like default_attributes.client.ldap_server
        :param item: final value
        :param array_build: this argument needed by function recursion
        :return: builded array (can contain dicts and lists)
        """

        # construction "if "." in keys:" is not going to work
        # since we need escape "\."
        splited_elements = re.split(r'(?<!\\)\.', keys, 1)  # keys.split(".", 1) with \. support
        if len(splited_elements) > 1:

            key, rest = splited_elements  # replacement for: key, rest = keys.split(".", 1)
            key = key.replace('\\', '')
            # print(key)

            if rest[:3] == '[].':
                # if next element in the dot tree is list, we want to create list
                desire_object = []
            else:
                desire_object = {}

            if key == '[]':
                # if current desire_object is list, let's append
                array_build.append(desire_object)
                build(rest, item, array_build[0])
            else:
                # otherwise it's a dict
                array_build[key] = desire_object
                build(rest, item, array_build[key])

        else:
            # = keys variable - last element in a dot tree
            # one.two.three.four.five
            #                     ^^ -- this one
            keys = keys.replace('\\', '')
            array_build[keys] = item

            return item

        return array_build

    structure = build(path, value, {})
    return structure


def modify_environment(current, patch, action, path=[]):
    """
    Upgrades current environment with a provided patch
    Merges "patch" into "current"

    :param current: full original json object aka nested dicts + lists
    :param patch: json attributes to upgrade in current JSON object
    :param action: set / unset
    :param path: attribute for recursion call
    :return: upgraded environment ;-)
    """

    for key in patch:

        if key in current:

            # We go deeper (recursion) only if this is a dict
            if isinstance(current[key], dict) and isinstance(patch[key], dict):
                modify_environment(current[key], patch[key], action, path + [str(key)])

            # If list we DO NOT go deeper even if there is another dict inside list
            elif isinstance(current[key], list) and isinstance(patch[key], list):

                if action == 'unset':
                    del current[key]
                elif action == 'set':
                    current[key] += patch[key]

            elif current[key] == patch[key]:
                # If values of keys the same between current and patch - do nothing

                if action == 'unset':
                    del current[key]

                # pass  # same leaf value
            else:
                # raise Exception('Conflict at %s' % '.'.join(path + [str(key)]))
                # -- Overwriting existing value
                if action == 'unset':
                    del current[key]
                elif action == 'set':
                    current[key] = patch[key]

        else:
            # -- Creating new key with value if it's not in current environment
            if action == 'set':
                current[key] = patch[key]

    return current


def view_environment(current, patch, path=[]):
    """
    Views current environment with a provided view patch
    Compares "patch" into "current"
    This is simplified version from modify_environment()

    :param current: full original json object aka nested dicts + lists
    :param patch: json attributes to follow in current JSON object
    :param path: attribute for recursion call
    :return: value environment
    """

    attribute_structure = {}

    for key in patch:

        if key in current:

            # We go deeper (recursion) only if this is a dict
            if isinstance(current[key], dict) and isinstance(patch[key], dict):
                attribute_structure = view_environment(current[key], patch[key], path + [str(key)])
            else:
                path.append(current[key])
                return path

    return attribute_structure


def environment_path(environments_location, environment_name):
    """
    
    :param environments_location: 
    :param environment_name: 
    :return: 
    """
    environment_file_ext = 'json'
    environment_fullpath = "{}/{}.{}".format(environments_location, environment_name, environment_file_ext)

    return environment_fullpath


def get_environment(environment_location):
    """

    :param environment_location:
    :return:
    """
    return json.loads(open(environment_location).read(), object_pairs_hook=OrderedDict)


def write_environment(environment_location, body, tab_space_num=2):
    """

    :param environment_location:
    :param body:
    :param tab_space_num:
    :return:
    """
    # open(environment_location, 'w').write(json.dumps(body, indent=tab_space_num))
    with open(environment_location, "w") as json_environment_file:
        json_environment_buffer = json.dumps(body, indent=tab_space_num, default="\n")
        json_environment_file.write("{}\n".format(json_environment_buffer))  # Add newline cause Py does not
    return True


def interactive_editor():
    """
    Use your favorite editor to provide a set of attributes

    :return: returns dict
    """

    editor = os.environ.get('EDITOR', 'vi')
    initial_message = "# Lines starting with '#' will be ignored\n" \
                      "# Please provide a full path, aka you\n" \
                      "# want to start from \"default_attributes\": {...}\n" \
                      "# Example: {\"default_attributes\": { \"rundeck\": {\"configuration\":" \
                      " {\"globalproxy.populate.mysql.connect_timeout_ms\": \"600000\", " \
                      "\"globalproxy.populate.mysql.socket_timeout_ms\": \"600000\"} }}}\n" \
                      "#\n\n"

    with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False, mode='w+') as tf:
        tf.write(initial_message)
        tf.flush()
        call([editor, tf.name])

        # tf.seek(0)
        # edited_message = tf.read()
        tf.close()

        # edited_message = open(tf.name).read()
        tem_file_strings_list = []

        # temp_file_second_open
        with open(tf.name) as temp_file_second_open:
            for tfs_line in temp_file_second_open:
                if tfs_line[0] == '#':
                    continue
                tem_file_strings_list.append(tfs_line.strip().strip("\n"))

        os.unlink(tf.name)

        edited_message = ''.join(tem_file_strings_list)

    return edited_message


def validate_json_syntax(json_data):
    """
    Simple validator for JSON syntax

    :param json_data: body of json
    :return: bool, true if syntax is ok
    """
    try:
        json.loads(json_data)
    except ValueError:
        return False
    return True


def main(arguments):

    parser = argparse.ArgumentParser(
        description="\033[93m[[ {} ]]\033[0m v.\033[92m {}\033[0m ".format(__doc__.upper(), __version__),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="example usage:\n"
               "\t%(prog)s -e WDC-Applovin -a set -m\n"
               "\t%(prog)s -g stage -a get -atr 'default_attributes.app.queues\\.async_postbacks\\.weight' \n"
               "\t%(prog)s \n"
    )
    parser.add_argument('--action', '-a', help='action to perform', type=str, dest='ACTION',
                        choices=['set', 'unset', 'get'], default='get'),
    parser.add_argument('--environment-group', '-g', type=str, dest='ENV_GR',
                        help='perform an action to a specific environment group'),
    parser.add_argument('--environment', '-e', type=str, dest='ENV_NAME',
                        help='perform an action to a single environment or environments separated by commas'),
    parser.add_argument('--environment-exclude', type=str, dest='ENV_EXCLUDE',
                        help='regex name to exclude any environment from group list'),
    parser.add_argument('--spork-config-file', '-c', help='path to config file to use', type=str, dest='PATH_CFG',
                        default=os.environ.get('CHEM_SPORK_CONFIG', ''))
    parser.add_argument('--env-path', help='path to a dir with environments', type=str, dest='PATH_ENV',
                        default=os.environ.get('CHEM_ENV_PATH', ''))
    parser.add_argument('--attribute', '-atr', help='dot tree representation', type=str, dest='ATTRIBUTE')
    parser.add_argument('--patch-interactive', '-m', dest='PATCH_MODE', action="store_true",
                        help='Make a patch using the editor specified by the EDITOR environment variable')
    parser.add_argument('--patch-from-file', '-p', type=str, dest='PATCH_FROM_FILE',
                        help='Merge a file which contains JSON object to a environment')
    args = parser.parse_args(arguments)

    # The mode to process
    if args.PATCH_MODE is True:
        modified_attributes_string = interactive_editor()

        if not validate_json_syntax(modified_attributes_string):
            parser.error('Provided JSON data has syntax error(s)')

        modified_attributes = json.loads(modified_attributes_string)
    elif args.ATTRIBUTE is not None:
        modified_attributes = attr_dict_new(args.ATTRIBUTE)
    elif args.PATCH_FROM_FILE is not None:
        json_data = open(args.PATCH_FROM_FILE).read()
        modified_attributes = json.loads(json_data)
    else:
        parser.error('You should provide an attribute path or enter to a patch mode')

    spork_config = load_config(args.PATH_CFG)
    env_groups = get_environment_groups(spork_config)

    if args.ENV_GR:
        env_group_current_list = env_groups[args.ENV_GR]
    elif args.PATH_ENV:
        # Split by commas and strip extra space if there is
        env_group_current_list = [x.strip() for x in args.ENV_NAME.split(',')]
    else:
        parser.error('You should specify an environment group or single environment name')

    for environment in env_group_current_list:

        if args.ENV_EXCLUDE is not None and environment.find(args.ENV_EXCLUDE) >= 0:
            continue

        print("Processing: {}".format(environment))

        env_file_full_path = environment_path(
            args.PATH_ENV,
            environment
        )

        env_data = get_environment(env_file_full_path)

        if args.ACTION == 'get':

            attribute_path = view_environment(env_data, modified_attributes)
            if not attribute_path:
                print("\033[0;31mNot found\033[0m")
                continue
            output = "{} : \033[93m{}\033[0m".format(
                " -> ".join(attribute_path[:-1]),
                attribute_path[-1]
            )
            print(output)

        else:
            env_data_modified = modify_environment(env_data, modified_attributes, args.ACTION)
            write_environment(env_file_full_path, env_data_modified)

            del env_data_modified


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
