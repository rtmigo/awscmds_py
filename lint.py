import subprocess


def lint():
    print("Running pylint...")
    r = subprocess.call(['pylint', 'awscmds'])
    if r & 1 or r & 2 or r & 32:
        exit(1)

    print("Running mypy...")
    if subprocess.call(['mypy', 'awscmds',
                        '--ignore-missing-imports']) != 0:
        exit(1)

if __name__ == "__main__":
    lint()