from chkpkg import Package

if __name__ == "__main__":
    with Package() as pkg:
        for name in ['docker_build',
                     'docker_stop',
                     'docker_push_to_ecr',
                     'docker_run',
                     'lambda_function_update',
                     'lambda_function_wait_updated',
                     'ecr_delete_images_all',
                     'ecr_delete_images_by_json',
                     'print_header',
                     'set_header_prefix',
                     'aws_create_credentials_file',
                     'aws_get_default_credentials_file_path',
                     'aws_create_credentials_file_on_need',
                     'runcp',
                     'LambdaDockerPipeline',
                     'Stage']:
            pkg.run_python_code(f'from awscmds import {name}')

    print("\nPackage is OK!")
