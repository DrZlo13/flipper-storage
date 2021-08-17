from flipper_storage_lib import FlipperStorage
import logging
import argparse
import os
import sys

class Main:
    def __init__(self):
        # command args
        self.parser = argparse.ArgumentParser()
        self.parser.add_argument("-d", "--debug", action="store_true", help="Debug")
        self.parser.add_argument("-p", "--port", help="CDC Port", required=True)
        self.subparsers = self.parser.add_subparsers(help="sub-command help")

        self.parser_mkdir = self.subparsers.add_parser("mkdir", help="Create directory")
        self.parser_mkdir.add_argument("-fp", "--flipper-path", help="Flipper path", required=True)
        self.parser_mkdir.set_defaults(func=self.mkdir)

        # logging
        self.logger = logging.getLogger()

    def __call__(self):
        self.args = self.parser.parse_args()
        if "func" not in self.args:
            self.parser.error("Choose something to do")
        # configure log output
        self.log_level = logging.DEBUG if self.args.debug else logging.INFO
        self.logger.setLevel(self.log_level)
        self.handler = logging.StreamHandler(sys.stdout)
        self.handler.setLevel(self.log_level)
        self.formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        self.handler.setFormatter(self.formatter)
        self.logger.addHandler(self.handler)
        # execute requested function
        self.args.func()

    def mkdir(self):
        storage = FlipperStorage(self.args.port)
        storage.start()
        self.logger.debug(f'Creating "{self.args.flipper_path}"')
        if not storage.mkdir(self.args.flipper_path):
            self.logger.error(f'Error: {storage.last_error}')
        storage.stop()

if __name__ == "__main__":
    Main()()