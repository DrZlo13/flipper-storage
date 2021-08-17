from flipper_storage_lib import FlipperStorage
import logging
import argparse
import os
import sys
import binascii

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

        self.parser_remove = self.subparsers.add_parser("remove", help="Remove file/directory")
        self.parser_remove.add_argument("-fp", "--flipper-path", help="Flipper path", required=True)
        self.parser_remove.set_defaults(func=self.remove)

        self.parser_read = self.subparsers.add_parser("read", help="Read file")
        self.parser_read.add_argument("-fp", "--flipper-path", help="Flipper path", required=True)
        self.parser_read.set_defaults(func=self.read)

        self.parser_receive = self.subparsers.add_parser("receive", help="Receive file")
        self.parser_receive.add_argument("-fp", "--flipper-path", help="Flipper path", required=True)
        self.parser_receive.add_argument("-lp", "--local-path", help="Local path", required=True)
        self.parser_receive.set_defaults(func=self.receive)

        self.parser_send = self.subparsers.add_parser("send", help="Send file")
        self.parser_send.add_argument("-fp", "--flipper-path", help="Flipper path", required=True)
        self.parser_send.add_argument("-lp", "--local-path", help="Local path", required=True)
        self.parser_send.set_defaults(func=self.send)

        self.parser_list = self.subparsers.add_parser("list", help="Recursively list files and dirs")
        self.parser_list.add_argument("-fp", "--flipper-path", help="Flipper path", default='/')
        self.parser_list.set_defaults(func=self.list)

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

    def remove(self):
        storage = FlipperStorage(self.args.port)
        storage.start()
        self.logger.debug(f'Removing "{self.args.flipper_path}"')
        if not storage.remove(self.args.flipper_path):
            self.logger.error(f'Error: {storage.last_error}')
        storage.stop()

    def receive(self):
        storage = FlipperStorage(self.args.port)
        storage.start()
        self.logger.debug(f'Receiving "{self.args.flipper_path}" to "{self.args.local_path}"')
        if not storage.receive_file(self.args.flipper_path, self.args.local_path):
            self.logger.error(f'Error: {storage.last_error}')
        storage.stop()

    def send(self):
        storage = FlipperStorage(self.args.port)
        storage.start()
        self.logger.debug(f'Sending "{self.args.local_path}" to "{self.args.flipper_path}"')
        if not os.path.isfile(self.args.local_path):
            self.logger.error(f'Error: local file is not exist')
        else:
            if not storage.send_file(self.args.local_path, self.args.flipper_path):
                self.logger.error(f'Error: {storage.last_error}')
        storage.stop()

    def read(self):
        storage = FlipperStorage(self.args.port)
        storage.start()
        self.logger.debug(f'Reading "{self.args.flipper_path}"')
        data = storage.read_file(self.args.flipper_path)
        if not data:
            self.logger.error(f'Error: {storage.last_error}')
        else:
            try:
                print("Text data:")
                print(data.decode())
            except:
                print("Binary hexadecimal data:")
                print(binascii.hexlify(data).decode())
        storage.stop()

    def list(self):
        storage = FlipperStorage(self.args.port)
        storage.start()
        self.logger.debug(f'Listing "{self.args.flipper_path}"')
        storage.list_tree(self.args.flipper_path)
        storage.stop()

if __name__ == "__main__":
    Main()()