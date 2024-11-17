import argparse
import logging
from pathlib import Path

from tqdm import tqdm

from rmtree.debug import test_assertion
from rmtree.struct.file import list_files

logger = logging.getLogger(__name__)


def get_verbosity(verbose: int):
    if verbose == 0:
        return logging.CRITICAL
    if verbose == 1:
        return logging.WARNING
    if verbose == 2:
        return logging.INFO
    if verbose >= 3:
        return logging.DEBUG


def main(args=None):
    # set up the arg parser
    parser = argparse.ArgumentParser("rmtree", description='Process the file tree of the reMarkable tablet.')
    parser.add_argument('src', type=Path, help='The source folder.')
    parser.add_argument('dst', type=Path, help='The folder where the files are exported to.',
                        nargs='?')
    parser.add_argument('--verbose', '-v', action='count', default=0, help='Increase verbosity.')
    parser.add_argument('--dependencies-verbosity', type=int, default=0,
                        help='Set verbosity of the dependencies.')
    parser.add_argument('--test-compatibility', '-t', action='store_true', default=False,
                        help='Test if the files from the reMarkable are compatible with this program.')
    parser.add_argument('--ignore-assertion', '-i', action='store_true', default=False,
                        help='If the program should continue despite assertion errors.'
                             'There will be no guarantee the output is correct.')

    args = parser.parse_args(args)

    if not (args.dst or args.test_compatibility):
        parser.error("Please specify 'dst' argument.")

    # set up the logging
    logging.basicConfig(level=logging.DEBUG if args.test_compatibility else get_verbosity(args.verbose))
    deps_verbosity = logging.DEBUG if args.test_compatibility else get_verbosity(args.dependencies_verbosity)
    logging.getLogger("rmscene").setLevel(deps_verbosity)
    logging.getLogger("rmc").setLevel(deps_verbosity)

    count_compatibility_errors, count_assertion_errors = test_assertion(args.src,
                                                                        print if args.test_compatibility else
                                                                        lambda *args: None)
    print(f"{count_compatibility_errors} detected compatibility errors.")
    print(f"{count_assertion_errors} detected assertion errors.")

    if ((not args.test_compatibility)
            and (count_assertion_errors == 0 or args.ignore_assertion)
            and count_compatibility_errors == 0):
        # export all the files
        files = list_files(args.src)
        progress = tqdm(files.items())
        for uuid, f in progress:
            progress.set_description(str(f))
            f.export(args.dst.joinpath(f.get_path(files)))


if __name__ == "__main__":
    main()
