# from termcolor import colored
import subprocess


def cyan(x):
    pass
    # print(colored(x, 'cyan'))


def yellow(x):
    pass
    # print(colored(x, 'yellow'))


def red(x):
    pass
    # print(colored(x, 'red'))


def just_deploy_linked(bytecode_file, private_key):
    subprocess.call(
        args=[
            'python',
            '../just-deploy/deploy_linked.py',
            bytecode_file,
            private_key,
            'http://localhost:8545',
            '--publish'])


def just_deploy(bytecode_file, private_key):
    subprocess.call(
        args=[
            'python',
            '../just-deploy/deploy.py',
            bytecode_file,
            private_key,
            'http://localhost:8545',
            '--publish'])


def long_string_to_list(x, size):
    return [('0x'+x[i:i+size]) for i in range(0, len(x), size)]


def csf_to_list(comma_separated_field, cast=None):
    if cast is None:
        return comma_separated_field.split(",")
    if not comma_separated_field or len(comma_separated_field) == 0:
        return []
    return [cast(x) for x in comma_separated_field.split(",")]


def str_int(x):
    return str(int(x))


class Singleton(type):
    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cls._instance = None

    def __call__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__call__(*args, **kwargs)
        return cls._instance


ZERO_CHECKSUM = '0000000000000000000000000000000000000000000000000000000000000000'
