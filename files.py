import filecmp
import os
import serial
import time
import hashlib

def timing(func):
    """
    Speedometer decorator
    """
    def wrapper(*args, **kwargs):
        time1 = time.monotonic()
        ret = func(*args, **kwargs)
        time2 = time.monotonic()
        print('{:s} function took {:.3f} ms'.format(func.__name__, (time2 - time1) * 1000.0))
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
        return self.read.until(self.CLI_EOL)

    def send_and_wait_prompt(self, line):
        self.send(line)
        return self.read.until(self.CLI_PROMPT)

    # Is data has error
    def has_error(self, data):
        if data.find(b'Storage error') != -1:
            return True
        else:
            return False

    # Extract error text from data and print it
    def get_error(self, data):
        return data.decode('ascii').split(': ')[1].strip()

    # List files and dirs on Flipper
    def list_tree(self, path="/", level=0):
        path = path.replace('//', '/')

        self.send_and_wait_eol('storage list "' + path + '"\r')

        data = self.read.until(self.CLI_PROMPT)
        data = data.split(b'\r\n')

        for line in data:
            try:
                # TODO: better decoding, considering non-ascii characters
                line = line.decode("ascii")
            except:
                continue

            line = line.strip()

            if len(line) == 0:
                continue

            if(self.has_error(line.encode())):
                print(self.get_error(line.encode()))
                continue

            if line == 'Empty':
                print('Empty')
                continue

            line = line.split(" ", 1)
            if(line[0] == '[D]'):
                # Print directory name
                print((path + '/' + line[1]).replace('//', '/'))
                # And recursively go inside
                self.list_tree(path + '/' + line[1], level + 1)
            elif(line[0] == '[F]'):
                line = line[1].rsplit(" ", 1)
                # Print file name and size
                print((path + '/' + line[0]).replace('//', '/') + ', size ' + line[1])
            else:
                # Somthing wrong
                pass

    # Send file from local device to Flipper
    def send_file(self, filename_from, filename_to):
        if self.remove(filename_to):
            print('Removed "' + filename_to + '"' )

        print('Sending "' + filename_from + '" > "' + filename_to + '"' )

        file = open(filename_from, 'rb')
        filesize = os.fstat(file.fileno()).st_size

        buffer_size = 512
        while True:
            filedata = file.read(buffer_size)
            size = len(filedata)
            if size == 0:
                break

            self.send_and_wait_eol('storage write_chunk "' + filename_to +  '" ' + str(size) + '\r')
            error = self.read.until(self.CLI_EOL)
            if(self.has_error(error)):
                print(self.get_error(error))
                self.read.until(self.CLI_PROMPT)
                file.close()
                return
            
            self.port.write(filedata)
            self.read.until(self.CLI_PROMPT)

            percent = str(round(file.tell() / filesize * 100))
            total_chunks = str(round(filesize / buffer_size))
            current_chunk = str(round(file.tell() / buffer_size))
            print(percent + '%, chunk ' + current_chunk + ' of ' + total_chunks, end='\r')
        file.close()
        print()

    # Receive file from Flipper, and get filedata (bytes)
    def read_file(self, filename):
        buffer_size = 512
        self.send_and_wait_eol('storage read_chunks "' + filename + '" ' + str(buffer_size) + '\r')
        size = self.read.until(self.CLI_EOL)
        filedata = bytearray()
        if self.has_error(size):
            print(self.get_error(size))
            self.read.until(self.CLI_PROMPT)
            return filedata
        size = int(size.split(b': ')[1])
        readed_size = 0

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
        print()
        self.read.until(self.CLI_PROMPT)
        return filedata

    # Receive file from Flipper to local storage
    def receive_file(self, filename_from, filename_to):
        with open(filename_to, 'wb') as file:
            file.write(self.read_file(filename_from))

    # Get hash of file on Flipper
    def hash_file(self, filename):
        self.send_and_wait_eol('storage md5 "' + filename + '"\r')
        hash = self.read.until(self.CLI_EOL)
        self.read.until(self.CLI_PROMPT)

        if self.has_error(hash):
            print(self.get_error(hash))
            return ''
        else:
            return hash.decode('ascii')

    # Is file or dir exist on Flipper
    def exist(self, path):
        self.send_and_wait_eol('storage stat "' + path + '"\r')
        answer = self.read.until(self.CLI_EOL)
        self.read.until(self.CLI_PROMPT)

        if self.has_error(answer):
            return False
        else:
            return True

    # Create a directory on Flipper
    def mkdir(self, path):
        self.send_and_wait_eol('storage mkdir "' + path + '"\r')
        answer = self.read.until(self.CLI_EOL)
        self.read.until(self.CLI_PROMPT)

        if self.has_error(answer):
            return False
        else:
            return True

    # Remove file or directory on Flipper
    def remove(self, path):
        self.send_and_wait_eol('storage remove "' + path + '"\r')
        answer = self.read.until(self.CLI_EOL)
        self.read.until(self.CLI_PROMPT)

        if self.has_error(answer):
            return False
        else:
            return True

# Hash of local file
def md5(fname):
    hash_md5 = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

LOCAL_FILE = '.gitignore'
LOCAL_FILE_TMP = LOCAL_FILE + '.tmp'
FILE_ON_FLIPPER = '/ext/' + LOCAL_FILE

if __name__ == '__main__':
    storage = FlipperStorage('COM16')
    storage.start()
    storage.send_file(LOCAL_FILE, FILE_ON_FLIPPER)
    storage.receive_file(FILE_ON_FLIPPER, LOCAL_FILE_TMP)

    hash = storage.hash_file(FILE_ON_FLIPPER)
    if(hash): print(hash)

    print(md5(LOCAL_FILE))

    if filecmp.cmp(LOCAL_FILE, LOCAL_FILE_TMP, False):
        print('OK')
    else:
        print('Error')
    os.remove(LOCAL_FILE_TMP)

    storage.list_tree()
    storage.stop()
