# SPDX-FileCopyrightText: (c) 2021 Artёm IG <github.com/rtmigo>
# SPDX-License-Identifier: MIT

import json
import re
import sys
import textwrap
import time
import unittest
from pathlib import Path
from subprocess import Popen, PIPE, CalledProcessError, \
    check_output, CompletedProcess, STDOUT
from typing import List, Union, Optional, Sequence, IO, Any, Dict


################################################################################

class HeaderPrinter:
    prefix: Optional[str] = None

    @classmethod
    def print_header(cls, s: str) -> None:
        print()
        print('/' * 80)
        if cls.prefix is not None:
            print('  ' + cls.prefix)

        print('  ' + s.upper())
        print('/' * 80)
        print()


print_header = HeaderPrinter.print_header


def set_header_prefix(prefix: str):
    HeaderPrinter.prefix = prefix


################################################################################

def runcp(args: Sequence[str],
          check=False,
          stdin: Optional[IO[Any]] = None,
          encoding: str = sys.stdout.encoding,
          errors='replace',
          env: Optional[Dict[str, str]] = None
          ) -> CompletedProcess:
    stdout_lines = []
    with Popen(args,
               stdout=PIPE,
               stderr=STDOUT,
               stdin=stdin,
               bufsize=1,
               encoding=encoding,
               errors=errors,
                env=env
               ) as process:
        assert process.stdout is not None

        while True:
            output = process.stdout.readline()
            assert isinstance(output, str)
            stdout_lines.append(output)
            if output == '' and process.poll() is not None:
                break
            if len(output) > 0:
                print(output, flush=True, end='')

        exit_code = process.wait()

        stdout_text = '\n'.join(stdout_lines)

        if check and exit_code != 0:
            raise CalledProcessError(returncode=exit_code, cmd=args,
                                     output=stdout_text)

        return CompletedProcess(args=args, returncode=exit_code,
                                stdout=stdout_text)


################################################################################


def check_call_rt(args: Sequence[str], stdin: Optional[IO[Any]] = None):
    return runcp(args, check=True, stdin=stdin)


def _combine(items: List) -> List[str]:
    args: List[str] = list()
    for item in items:
        if isinstance(item, str):
            args.append(item)
        elif isinstance(item, (list, tuple)):
            args.extend(item)
        elif item is None:
            continue
        else:
            raise TypeError(item)
    return args


def _is_docker_build_too_many_requests(cp: CompletedProcess) -> bool:
    # Sometimes in GitHub Actions I get
    # "Step 1/8 : FROM public.ecr.aws/lambda/python:3.8 AS base-image
    #  toomanyrequests: Rate exceeded"
    tmr = 'toomanyrequests: Rate exceeded'
    # (tmr in cp.stdout or tmr in cp.stderr)
    return cp.returncode != 0 and tmr in cp.stderr


def docker_build(source_dir: Path, image_name: str,
                 docker_file: Path = None,
                 tmr_timeout: float = 30) -> None:
    start_time = time.monotonic()

    print_header(f'Building docker image {image_name}')
    args = _combine([
        'docker', 'build', '-t', image_name,
        ['-f', str(docker_file)] if docker_file else None,
        str(source_dir)
    ])

    while True:
        # pylint: disable=subprocess-run-check
        cp = runcp(args)  # , capture_output=True, encoding='utf-8'
        if cp.returncode == 0:
            return
        assert cp.returncode != 0
        if _is_docker_build_too_many_requests(cp) and \
                (time.monotonic() - start_time) < (tmr_timeout - 1):
            print("Got 'too many requests' error. Will retry...")
            time.sleep(1)
            continue
        raise CalledProcessError(cp.returncode, cp.args,
                                 cp.stdout, cp.stderr)


def docker_run(image_name: str, container_name: str = None,
               detach: bool = False,
               port_host: int = None,
               port_docker: int = None):
    print_header(
        f"Starting docker image {image_name} (container: {container_name})")

    port_mapping: Optional[str]
    if port_host is not None or port_docker is not None:
        if port_host is None or port_docker is None:
            raise ValueError(
                "Both or none of [port_host, port_docker] must be specified")
        port_mapping = str(port_host) + ':' + str(port_docker)
    else:
        port_mapping = None

    command = _combine([
        'docker', 'run', '--rm',
        '-d' if detach else None,
        ('-p', port_mapping) if port_mapping else None,
        ('--name', container_name) if container_name else None,
        image_name])

    check_call_rt(command)


def docker_stop(container_name: str):
    print_header(f"Stopping docker container {container_name}")
    check_call_rt(('docker', 'container', 'stop', container_name))


class EcrRepoUri:
    def __init__(self, uri: str):
        self.uri = uri

        m = re.match(r'(.+)/([^@:]+)(?:[@:](.+))?', uri)
        if m is None:
            raise ValueError(uri)
        self.host = str(m.group(1))
        self.name = str(m.group(2))
        self.tag = str(m.group(3)) if m.group(3) else None
        self.region = self.host.split('.')[-3]

    @property
    def uri_without_tag(self):
        return self.host + '/' + self.name

    def __str__(self):
        return self.uri


class TestEcrRepoUri(unittest.TestCase):
    def test_with_tag(self):
        src = '1253812538.dkr.ecr.us-east-1.amazonaws.com/abc_x1:mytag'
        uri = EcrRepoUri(src)
        self.assertEqual(uri.host, '1253812538.dkr.ecr.us-east-1.amazonaws.com')
        self.assertEqual(uri.name, 'abc_x1')
        self.assertEqual(uri.tag, 'mytag')
        self.assertEqual(uri.region, 'us-east-1')
        self.assertEqual(uri.uri_without_tag,
                         '1253812538.dkr.ecr.us-east-1.amazonaws.com/abc_x1')

    def test_without_tag(self):
        src = '1253812538.dkr.ecr.us-east-1.amazonaws.com/abc_x1'
        uri = EcrRepoUri(src)
        self.assertEqual(uri.host, '1253812538.dkr.ecr.us-east-1.amazonaws.com')
        self.assertEqual(uri.name, 'abc_x1')
        self.assertEqual(uri.region, 'us-east-1')
        self.assertEqual(uri.tag, None)
        self.assertEqual(uri.uri_without_tag,
                         '1253812538.dkr.ecr.us-east-1.amazonaws.com/abc_x1')

    def test_with_sha(self):
        src = '61298361286.dkr.ecr.us-east-1.amazonaws.com' \
              '/imagename@sha256:d13b68bf5763e3cf8b9898d4c2b' \
              '5000ad538e8d4155ef80686e0c3f04322c9af'
        uri = EcrRepoUri(src)
        self.assertEqual(uri.name, 'imagename')
        self.assertTrue(uri.tag.startswith('sha256:d13b68'))


def ecr_repo_uri_to_region(uri: str) -> str:
    parts = uri.split('/')
    host = next(p for p in parts if p.endswith('.amazonaws.com'))
    return host.split('.')[-3]


assert ecr_repo_uri_to_region(
    "1253812538.dkr.ecr.us-east-1.amazonaws.com/abc") == 'us-east-1'


def _get_digest(output: str) -> str:
    m = re.search(r'digest: (sha256:[0-9a-z]+)', output)
    if not m:
        raise ValueError(m)
    return str(m.group(1))


class TestGetDigest(unittest.TestCase):
    def test(self):
        s = _get_digest('''
            30472d65e424: Pushed
            95e3c2813def: Pushed
            latest: digest: sha256:d4c7852abfabaf3076bd6a84 size: 2841
        ''')
        self.assertEqual(s, 'sha256:d4c7852abfabaf3076bd6a84')


def ecr_delete_images_by_json(repo_uri: Union[EcrRepoUri, str],
                              image_ids_in_json: str):
    if isinstance(repo_uri, str):
        repo_uri = EcrRepoUri(repo_uri)

    if not json.loads(image_ids_in_json):
        print("Nothing to delete")
        return

    check_call_rt(('aws', 'ecr', 'batch-delete-image',
                   '--region', repo_uri.region,
                   '--repository-name', repo_uri.name,
                   '--image-ids', image_ids_in_json))


def ecr_get_untagged_images_json(repo_uri: Union[str, EcrRepoUri]) -> str:
    if isinstance(repo_uri, str):
        repo_uri = EcrRepoUri(repo_uri)

    cp = runcp((
        'aws', 'ecr', 'list-images',
        '--region', repo_uri.region,
        '--repository-name', repo_uri.name,
        '--filter', "tagStatus=UNTAGGED",
        '--query', 'imageIds[*]',
        '--output', 'json'

    ), check=True)

    # if cp.returncode != 0:
    #     raise CalledProcessError(cp.returncode, cp.args,
    #                              cp.stdout, cp.stderr)
    return cp.stdout


def ecr_delete_images_untagged(repo_uri: Union[str, EcrRepoUri]):
    js = ecr_get_untagged_images_json(repo_uri)
    return ecr_delete_images_by_json(repo_uri, js)


def ecr_delete_images_all(repo_uri: Union[EcrRepoUri, str]):
    print_header(f"Deleting all images from {str(repo_uri)}")

    if isinstance(repo_uri, str):
        repo_uri = EcrRepoUri(repo_uri)

    js = check_output((
        'aws', 'ecr', 'list-images',
        '--region', repo_uri.region,
        '--repository-name', repo_uri.name,
        '--query', 'imageIds[*]',
        '--output', 'json'

    ), encoding="utf-8")

    ecr_delete_images_by_json(repo_uri, js)


def docker_push_to_ecr(docker_image: str,
                       repo_uri: Union[EcrRepoUri, str]):
    """
    :param repo_uri: '1253812538.dkr.ecr.us-east-1.amazonaws.com/abc:mytag'
    :param docker_image: 'abc:mytag'

    When we push abc:mytag, it will be accessible with both
    1) ...amazonaws.com/abc:mytag (the repo_uri)
    2) ...amazonaws.com/abc@sha256:...

    The function returns the second one.
    """

    if isinstance(repo_uri, str):
        repo_uri = EcrRepoUri(repo_uri)

    with Popen(
            ('aws', 'ecr', 'get-login-password',
             '--region', repo_uri.region),
            stdout=PIPE) as get_password:
        check_call_rt(
            ('docker', 'login',
             '--username', 'AWS',
             '--password-stdin',
             repo_uri.host),
            stdin=get_password.stdout)

    check_call_rt((
        'docker', 'tag', docker_image,
        # repo_uri.uri_without_tag ?!
        repo_uri.uri
    ))

    # pylint: disable=subprocess-run-check
    cp = runcp((
        'docker', 'push', repo_uri.uri
    ))
    if cp.returncode != 0:
        print("Captured before error:")
        print("stdout:", cp.stdout)
        print("stderr:", cp.stderr)
        raise CalledProcessError(cp.returncode, cp.args)

    digest = _get_digest(cp.stdout)
    alternate_image_uri = repo_uri.uri_without_tag + '@' + digest
    print(f"Pushed image URI: {alternate_image_uri}")
    return alternate_image_uri


def lambda_function_wait_updated(aws_region: str, func_name: str):
    # Waits for the function's LastUpdateStatus to be Successful.
    # It will poll every 5 seconds until a successful state has
    # been reached. This will exit with a return code of 255 after
    # 60 failed checks
    print(f"Waiting for successful update status "
          f"of {func_name} at {aws_region}", flush=True)
    check_call_rt((
        'aws', 'lambda', 'wait', 'function-updated',
        '--region', aws_region,
        '--function-name', func_name))


def lambda_function_update(aws_region: str, func_name: str,
                           ecr_image_uri: Union[EcrRepoUri, str]):
    # ecr_image_uri can be an uri with hash code:
    # 61298361286.dkr.ecr.us-east-1.amazonaws.com/imagename@sha256:d13b68bf5763e3cf8b9898d4c2b5000ad538e8d4155ef80686e0c3f04322c9af

    ecr_image_uri = str(ecr_image_uri)

    print(f"Updating function {func_name} at {aws_region}")
    print(f"Image: {ecr_image_uri}")
    print()

    # when we call update-function-code twice in a row,
    # we can get "The operation cannot be performed at this time.
    # An update is in progress for resource". So we'll wait here...
    lambda_function_wait_updated(aws_region, func_name)

    check_call_rt((
        'aws', 'lambda', 'update-function-code',
        '--region', aws_region,
        '--function-name', func_name,
        '--image-uri', ecr_image_uri
    ))

    lambda_function_wait_updated(aws_region, func_name)
    print(f"Function {func_name} updated")


def aws_get_default_credentials_file_path() -> Path:
    # https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html
    # 2021: The credentials file is located at ~/.aws/credentials on Linux or macOS,
    # or at C:\Users\USERNAME\.aws\credentials on Windows.

    return Path.home() / '.aws' / 'credentials'


def aws_create_credentials_file(
        access_key_id: str,
        secret_access_key: str,
        overwrite: bool = False,
        file: Path = None) -> Path:
    """Creates ~/.aws/credentials file with the values provided."""

    file = file or aws_get_default_credentials_file_path()

    if not overwrite and file.exists():
        raise FileExistsError
    file.parent.mkdir(exist_ok=True, parents=True)
    txt = f'''
        [default]
        aws_access_key_id = {access_key_id}
        aws_secret_access_key = {secret_access_key}
    '''
    file.write_text(textwrap.dedent(txt).strip())
    return file


def aws_create_credentials_file_on_need(
        access_key_id: Optional[str],
        secret_access_key: Optional[str]) -> Path:
    """If there are no ~/.aws/credentials file, this function will try to
    create it from the arguments.

    It can be used in simulated environments such as GitHub Actions.

    Sample usage:
        file = aws_create_credentials_file_on_need(
            os.environ.get("AWS_MY_ACCESS_KEY_ID"),
            os.environ.get("AWS_MY_SECRET_ACCESS_KEY"))
    """
    aws_cred_file = aws_get_default_credentials_file_path()
    if not aws_cred_file.exists():
        if access_key_id is None:
            raise ValueError('access_key_id is None, '
                             'and no credentials file')
        if secret_access_key is None:
            raise ValueError('secret_access_key is None, '
                             'and no credentials file')
        aws_create_credentials_file(access_key_id, secret_access_key)
    assert aws_cred_file.exists()
    return aws_cred_file


if __name__ == "__main__":
    unittest.main()
