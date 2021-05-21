# Copyright (c) 2021 Artёm IG <github.com/rtmigo>

import json
import sys
from argparse import ArgumentParser
from enum import IntEnum, auto
from inspect import signature
from pathlib import Path
from subprocess import check_call, check_output, Popen, PIPE
from typing import List, Callable, Union
from ._funcs import docker_build, docker_push_to_ecr, \
    ecr_delete_images_untagged, lambda_function_update, \
    lambda_function_wait_updated


class Stage(IntEnum):
    local = auto()
    docker = auto()
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
                 docker_file: Union[None, str, Path] = None):

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
            self.docker_file = Path(f'{docker_source_dir}/Dockerfile')
        else:
            self.docker_file = Path(docker_file)

    def header(self, s: str) -> None:
        print()
        print('/' * 80)
        print('  ' + s.upper())
        print('/' * 80)
        print()

    @property
    def ecr_region(self):
        return self.ecr_host.split('.')[-3]

    def _build_container(self):
        self.header("Building Docker image")
        docker_build(image_name=self.docker_image_name,
                     docker_file=self.docker_file,
                     source_dir=Path('.'))

    def _ecr_image_uri(self, stage: Stage):
        if stage == Stage.dev:
            return f"{self.ecr_host}/{self.ecr_repo_name}:dev"
        elif stage == Stage.prod:
            return f"{self.ecr_host}/{self.ecr_repo_name}:prod"
        else:
            raise ValueError(stage)

    def _lambda_func_name(self, stage: Stage):
        if stage == Stage.dev:
            return self.lambda_func_name_dev
        elif stage == Stage.prod:
            return self.lambda_func_name_prod
        else:
            raise ValueError(stage)

    def _push_container(self, stage: Stage):
        # pushes the last built image to Amazon ECR
        self.header(f"Pushing Docker image {stage.name}")

        docker_push_to_ecr(
            docker_image=self.docker_image_name,
            repo_uri=self._ecr_image_uri(stage))

    def _delete_untagged_ecr_images(self):
        self.header('Deleting untagged ECR images')
        ecr_delete_images_untagged(self.ecr_repo_name)

    def _update_function(self, stage: Stage):
        func_name = self._lambda_func_name(stage)
        image = self._ecr_image_uri(stage)

        self.header(f"Updating function {stage.name}")

        print(f"Function name: {func_name}")
        print(f"Image: {image}")
        print()

        # when we call update-function-code twice in a row,
        # we can get "The operation cannot be performed at this time.
        # An update is in progress for resource". So we'll wait here...
        lambda_function_wait_updated(self.aws_region, func_name)

        lambda_function_update(self.aws_region, func_name, image)
        lambda_function_wait_updated(self.aws_region, func_name)

    def _print_not_testing(self, method: Callable):
        print(f"{Colors.RED}Not testing. "
              f"Override {self.__class__.__name__}.{method.__name__} to run "
              f"this test.{Colors.END}")

    def test_docker(self):
        self._print_not_testing(self.test_docker)

    def test_dev(self):
        self._print_not_testing(self.test_dev)

    def test_prod(self):
        self._print_not_testing(self.test_prod)

    def test_local(self):
        self._print_not_testing(self.test_local)

    # def _test_local(self):
    #     self.header("Testing Local")
    #     self.test_local()
    #
    # def _test_docker(self):
    #     self.header("Testing Docker")
    #     self.test_docker()
    #
    # def _test_dev(self):
    #     self.header("Testing Dev")
    #     self.test_dev()
    #
    # def _test_prod(self):
    #     self.header("Testing Prod")
    #     self.test_prod()

    def build_docker(self):
        self._build_container()
        self.test_docker()

    def build_dev(self):
        self.build_docker()
        self._push_container(Stage.dev)
        self._update_function(Stage.dev)
        self.test_dev()

    def build_prod(self):
        self.build_dev()
        self._push_container(Stage.prod)
        self._update_function(Stage.prod)
        self.test_prod()

    def main(self):

        # finding all public methods that do not require args
        methods = []
        for x in dir(self):
            method = getattr(self, x)
            # skipping non-methods
            if not callable(method):
                continue
            # skipping private methods
            if method.__name__.startswith("_"):
                continue
            # skipping constructor
            if method.__name__ == self.__class__.__name__:
                continue
            # skipping `main`
            if method.__name__ == self.main.__name__:
                continue
            if signature(method).parameters:  # if has args
                continue
            methods.append(method)

        for method in methods:
            if len(sys.argv) >= 2 and sys.argv[1] == method.__name__:
                method()
                exit(1)

        print(f"Usage: {sys.argv[0]} [{' '.join(m.__name__ for m in methods)}]")


