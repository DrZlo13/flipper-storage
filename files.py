import filecmp
import os
import serial
import time

LOCAL_FILE = '1000k.txt'
LOCAL_FILE_TMP = LOCAL_FILE + '.tmp'
FILE_ON_FLIPPER = '/ext/' + LOCAL_FILE


def timing(func):
    """
    Speedometer decorator
    """
    def wrapper(*args, **kwargs):
        time1 = time.monotonic()
        ret = func(*args, **kwargs)
        time2 = time.monotonic()
        print('{:s} function took {:.3f} ms'.format(func, (time2 - time1) * 1000.0))
        return ret
    return wrapper


class BufferedRead:
    def __init__(self, stream):
        self.buffer = bytearray()
        self.stream = stream

    def until(self, eol='\n', cut_eol=True):
        eol = eol.encode()
        while True:
            # search in buffer
            i = self.buffer.find(eol)
            if i >= 0:
                if cut_eol:
                    read = self.buffer[:i]
                else:
                    read = self.buffer[:i + len(eol)]
                self.buffer = self.buffer[i + len(eol):]
                return read

            # read and append to buffer
            i = max(1, self.stream.in_waiting)
            data = self.stream.read(i)
            self.buffer.extend(data)


class FlipperStorage:
    CLI_PROMPT = '>: '
    CLI_SOH = '\x01'
    CLI_EOL = '\r\n'

    def __init__(self, portname: str):
        self.port = serial.Serial()
        self.port.port = portname
        self.port.timeout = 2
        self.port.baudrate = 115200
        self.read = BufferedRead(self.port)

    def start(self):
        self.port.open()
        self.send_and_wait_prompt(self.CLI_SOH)

    def stop(self):
        self.port.close()

    def send(self, line):
        self.port.write(line.encode())

    def send_and_wait_eol(self, line):
        self.send(line)
        self.read.until(self.CLI_EOL)

    def send_and_wait_prompt(self, line):
        self.send(line)
        self.read.until(self.CLI_PROMPT)

    def list_tree(self, path="/", level=0):
        path = path.replace('//', '/')

        self.send_and_wait_eol('storage list "' + path + '"\r')

        data = self.read.until(self.CLI_PROMPT)
        data = data.split(b'\r\n')

        for line in data:
            try:
                # TODO: better decoding, considering non-ascii characters, add an exception
                line = line.decode("ascii")
            except:
                continue

            line = line.strip()

            if len(line) == 0:
                continue

            print('  ' * level, end='')

            if line.find('Storage error') != -1:
                line = line.split(': ')
                print('Error: ' + line[1])
                continue

            if line == 'Empty':
                print('Empty')
                continue

            line = line.split(" ", 1)
            if line[0] == '[D]':
                print('/' + line[1])
                self.list_tree(path + '/' + line[1], level + 1)
            else:
                line = line[1].rsplit(" ", 1)
                print(line[0] + ', size ' + line[1])

    @timing
    def send_file(self, filename_from, filename_to):
        self.send_and_wait_prompt('storage remove "' + filename_to + '"\r')

        file = open(filename_from, 'rb')
        filesize = os.fstat(file.fileno()).st_size

        buffer_size = 512
        while True:
            filedata = file.read(buffer_size)
            size = len(filedata)
            if size == 0:
                break

            self.send_and_wait_eol('storage write_chunk "' + filename_to +  '" ' + str(size) + '\r')
            self.read.until('Ready' + self.CLI_EOL)

            self.port.write(filedata)
            self.read.until(self.CLI_PROMPT)

            percent = str(round(file.tell() / filesize * 100))
            total_chunks = str(round(filesize / buffer_size))
            current_chunk = str(round(file.tell() / buffer_size))
            print(percent + '%, chunk ' + current_chunk + ' of ' + total_chunks, end='\r')
        file.close()
        print()

    def read_file(self, filename):
        buffer_size = 512
        self.send_and_wait_eol('storage read_chunks "' + filename + '" ' + str(buffer_size) + '\r')
        size = self.read.until(self.CLI_EOL)
        size = int(size.split(b': ')[1])
        readed_size = 0
        filedata = bytearray()

        while readed_size < size:
            self.read.until('Ready?' + self.CLI_EOL)
            self.send('y')
            read_size = min(size - readed_size, buffer_size)
            filedata.extend(self.port.read(read_size))
            readed_size = readed_size + read_size

            percent = str(round(readed_size / size * 100))
            total_chunks = str(round(size / buffer_size))
            current_chunk = str(round(readed_size / buffer_size))
            print(percent + '%, chunk ' + current_chunk + ' of ' + total_chunks, end='\r')
        return filedata

    @timing
    def receive_file(self, filename_from, filename_to):
        with open(filename_to, 'wb') as file:
            file.write(self.read_file(filename_from))


if __name__ == '__main__':
    storage = FlipperStorage('COM16')
    storage.start()
    storage.send_file(LOCAL_FILE, FILE_ON_FLIPPER)
    storage.receive_file(FILE_ON_FLIPPER, LOCAL_FILE_TMP)

    if filecmp.cmp(LOCAL_FILE, LOCAL_FILE_TMP, False):
        print('OK')
    else:
        print('Error')
    os.remove(LOCAL_FILE_TMP)

    # file.list_tree()
    storage.stop()
