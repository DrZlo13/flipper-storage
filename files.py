import os, serial, filecmp, time

def timing(f):
    def wrap(*args, **kwargs):
        time1 = time.time()
        ret = f(*args, **kwargs)
        time2 = time.time()
        print('{:s} function took {:.3f} ms'.format(f.__name__, (time2-time1)*1000.0))

        return ret
    return wrap

class BufferedRead:
    def __init__(self, stream):
        self.buffer = bytearray()
        self.stream = stream
    
    def until(self, eol = '\n', cut_eol = True):
        eol = eol.encode()
        while True:
            # search in buffer
            i = self.buffer.find(eol)
            if i >= 0:
                if(cut_eol):
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

    def __init__(self, portname):
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

    def list_tree(self, path = "/", level = 0):
        path = path.replace('//', '/')

        self.send_and_wait_eol('storage list "' + path +  '"\r')

        data = self.read.until(self.CLI_PROMPT)
        data = data.split(b'\r\n')

        for line in data:
            try:
                # TODO: better decoding, considering non-ascii characters
                line = line.decode("ascii")
            except:
                continue

            line = line.strip()

            if(len(line) == 0):
                continue

            print('  ' * level, end = '')

            if(line.find('Storage error') != -1):
                line = line.split(': ')
                print('Error: ' + line[1])
                continue

            if(line == 'Empty'):
                print('Empty')
                continue

            line = line.split(" ", 1)
            if(line[0] == '[D]'):
                print('/' + line[1])
                self.list_tree(path + '/' + line[1], level + 1)
            else:
                line = line[1].rsplit(" ", 1)
                print(line[0] + ', size ' + line[1])

    @timing
    def send_file(self, filename_from, filename_to):
        self.send_and_wait_prompt('storage remove "' + filename_to +  '"\r')

        file = open(filename_from, 'rb')
        filesize = os.fstat(file.fileno()).st_size

        BUFFER_SIZE = 512
        while True:
            filedata = file.read(BUFFER_SIZE)
            size = len(filedata)
            if(size == 0):
                break

            self.send_and_wait_eol('storage write_chunk "' + filename_to +  '" ' + str(size) + '\r')
            self.read.until('Ready' + self.CLI_EOL)

            self.port.write(filedata)
            self.read.until(self.CLI_PROMPT)

            percent = str(round(file.tell() / filesize * 100))
            total_chunks = str(round(filesize / BUFFER_SIZE)) 
            current_chunk = str(round(file.tell() / BUFFER_SIZE)) 
            print(percent + '%, chunk ' + current_chunk + ' of ' + total_chunks, end='\r')
        file.close()
        print()

    def read_file(self, filename):
        BUFFER_SIZE = 512
        self.send_and_wait_eol('storage read_chunks "' + filename + '" ' + str(BUFFER_SIZE) + '\r')
        size = self.read.until(self.CLI_EOL)
        size = int(size.split(b': ')[1])
        readed_size = 0
        filedata = bytearray()

        while readed_size < size:
            self.read.until('Ready?' + self.CLI_EOL)
            self.send('y')
            read_size = min(size - readed_size, BUFFER_SIZE)
            filedata.extend(self.port.read(read_size))
            readed_size = readed_size + read_size

            percent = str(round(readed_size / size * 100))
            total_chunks = str(round(size / BUFFER_SIZE))
            current_chunk = str(round(readed_size / BUFFER_SIZE))
            print(percent + '%, chunk ' + current_chunk + ' of ' + total_chunks, end='\r')

        print()
        return filedata

    @timing
    def receive_file(self, filename_from, filename_to):
        file = open(filename_to, 'wb')
        file.write(self.read_file(filename_from))
        file.close()

FILE_HERE = '1000k.txt'
FILE_HERE_TMP = FILE_HERE + '.tmp'
FILE_ON_FLIPPER = '/ext/' + FILE_HERE

file = FlipperStorage('COM16')
file.start()
file.send_file(FILE_HERE, FILE_ON_FLIPPER)
file.receive_file(FILE_ON_FLIPPER, FILE_HERE_TMP)

if(filecmp.cmp(FILE_HERE, FILE_HERE_TMP, False)):
    print('OK')
else:
    print('Error')
os.remove(FILE_HERE_TMP)

#file.list_tree()
file.stop()