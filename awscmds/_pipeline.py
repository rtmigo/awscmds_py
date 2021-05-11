# Copyright (c) 2021 Artёm IG <github.com/rtmigo>

import json
from argparse import ArgumentParser
from enum import IntEnum, auto
from subprocess import check_call, check_output, Popen, PIPE
from typing import List


class Stage(IntEnum):
    dev = auto()
    prod = auto()


class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    END = '\033[0m'


class LambdaDockerPipeline:
    def __init__(self,
                 docker_image_name: str,
                 # Elastic Container Registry
                 erc_host: str,
                 ecr_repo_name: str,
                 # Lambda Functions
                 lambda_func_name_dev: str,
                 lambda_func_name_prod: str,

                 aws_region: str = None,
                 docker_source_dir: str = ".",
                 docker_file: str = None):

        self.docker_image_name = docker_image_name

        if aws_region:
            self.aws_region = aws_region
        else:
            self.aws_region = erc_host.split('.')[-3]
            assert self.aws_region[-1].isdigit()  # "us-east-1"

        self.ecr_host = erc_host
        self.ecr_repo_name = ecr_repo_name
        # self.ecr_dev_image_uri = f"{erc_host}/{ecr_repo_name}:dev"
        # self.ecr_prod_image_uri = f"{erc_host}/{ecr_repo_name}:prod"

        # Lambda Functions
        self.lambda_func_name_dev = lambda_func_name_dev
        self.lambda_func_name_prod = lambda_func_name_prod

        if docker_file is None:
            docker_file = f'{docker_source_dir}/Dockerfile'
        self.docker_file = docker_file

    def hdr(self, s: str) -> None:
        print()
        print('/' * 80)
        print('  ' + s.upper())
        print('/' * 80)
        print()

    @property
    def ecr_region(self):
        return self.ecr_host.split('.')[-3]

    def build_container(self):
        # todo call func
        # builds new docker image and stores it locally
        self.hdr("Building Docker image")

        check_call(
            ['docker', 'build', '-t', self.docker_image_name, '-f',
             self.docker_file, '.'])

    def ecr_image_uri(self, stage: Stage):
        if stage == Stage.dev:
            return f"{self.ecr_host}/{self.ecr_repo_name}:dev"
        elif stage == Stage.prod:
            return f"{self.ecr_host}/{self.ecr_repo_name}:prod"
        else:
            raise ValueError(stage)

    def lambda_func_name(self, stage: Stage):
        if stage == Stage.dev:
            return self.lambda_func_name_dev
        elif stage == Stage.prod:
            return self.lambda_func_name_prod
        else:
            raise ValueError(stage)

    def push_container(self, stage: Stage):
        # todo call func
        # pushes the last built image to Amazon ECR

        self.hdr(f"Pushing Docker image {stage.name}")

        image_uri = self.ecr_image_uri(stage)
        print(f"Image URI: {image_uri}")

        with Popen(
                ('aws', 'ecr', 'get-login-password',
                 '--region', self.aws_region),
                stdout=PIPE) as get_password:
            check_call(
                ('docker', 'login', '--username', 'AWS', '--password-stdin',
                 self.ecr_host),
                stdin=get_password.stdout)

        check_call((
            'docker', 'tag', f"{self.docker_image_name}:latest",
            image_uri
        ))

        check_call((
            'docker', 'push', image_uri
        ))

    def delete_untagged_ecr_images(self):
        # todo call func
        self.hdr('Deleting untagged ECR images')

        js = check_output((

            'aws', 'ecr', 'list-images',
            '--region', self.ecr_region,
            '--repository-name', self.ecr_repo_name,
            '--filter', "tagStatus=UNTAGGED",
            '--query', 'imageIds[*]',
            '--output', 'json'

        ), encoding="utf-8")

        if json.loads(js):
            check_call((
                'aws', 'ecr', 'batch-delete-image',
                '--region', self.ecr_region,
                '--repository-name', self.ecr_repo_name,
                '--image-ids', js))
        else:
            print("Nothing to delete")

    def update_function(self, stage: Stage):
        # todo call func
        func_name = self.lambda_func_name(stage)
        image = self.ecr_image_uri(stage)

        self.hdr(f"Updating function {stage.name}")

        print(f"Function name: {func_name}")
        print(f"Image: {image}")
        print()

        # when we call update-function-code twice in a row,
        # we can get "The operation cannot be performed at this time.
        # An update is in progress for resource". So we'll wait here...
        self._wait_last_update_status(func_name)

        check_call((
            'aws', 'lambda', 'update-function-code',
            '--region', self.aws_region,
            '--function-name', func_name,
            '--image-uri', image
        ))

        self._wait_last_update_status(func_name)

    def _wait_last_update_status(self, func_name: str):
        # todo call func
        print("Waiting for the function's LastUpdateStatus to be Successful")
        # Waits for the function's LastUpdateStatus to be Successful.
        # It will poll every 5 seconds until a successful state has
        # been reached. This will exit with a return code of 255 after
        # 60 failed checks
        check_call((
            'aws', 'lambda', 'wait', 'function-updated',
            '--region', self.aws_region,
            '--function-name', func_name))

    def test_docker(self):
        print(f"{Colors.RED}Not testing Docker. "
              f"Override Pipeline.test_docker to run tests.{Colors.END}")

    def test_dev(self):
        print(f"{Colors.RED}Not testing Dev. "
              f"Override Pipeline.test_dev to run tests.{Colors.END}")

    def test_prod(self):
        print(f"{Colors.RED}Not testing Dev. "
              f"Override Pipeline.test_dev to run tests.{Colors.END}")

    def _test_docker(self):
        self.hdr("Testing Docker")
        self.test_docker()

    def _test_dev(self):
        self.hdr("Testing Dev")
        self.test_dev()

    def _test_prod(self):
        self.hdr("Testing Prod")
        self.test_prod()

    def _build_and_upload_dev(self):
        self.build_container()
        self._test_docker()
        self.push_container(Stage.dev)
        self.update_function(Stage.dev)
        self._test_dev()

    def main(self):
        parser = ArgumentParser()
        parser.add_argument('command', choices=['dev', 'prod', 'build'])
        args = parser.parse_args()

        if args.command == 'build':
            self.build_container()
            self._test_docker()
        elif args.command == 'dev':
            self._build_and_upload_dev()
        elif args.command == 'prod':
            self._build_and_upload_dev()
            self.push_container(Stage.prod)
            self.update_function(Stage.prod)
            self.test_prod()
        else:
            raise ValueError(args.command)
