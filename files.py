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
        self.send(self.CLI_SOH)
        self.read.until(self.CLI_PROMPT)

    def stop(self):
        self.port.close()

    def send(self, line):
        self.port.write(line.encode())
        #print(line.encode(), end = '')

    def list_tree(self, start = "/", level = 0):
        start = start.replace('//', '/')

        self.send('storage list ' + start +  '\r')

        self.read.until(self.CLI_EOL)
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
                self.list_tree(start + '/' + line[1], level + 1)
            else:
                line = line[1].rsplit(" ", 1)
                print(line[0] + ', size ' + line[1])

    def send_file(self, filename_from, filename_to):
        self.send('storage remove ' + filename_to +  '\r')
        self.read.until(self.CLI_PROMPT)

        file = open(filename_from, 'rb+')
        filesize = os.fstat(file.fileno()).st_size

        BUFFER_SIZE = 512
        while True:
            filedata = file.read(BUFFER_SIZE)
            if(len(filedata) == 0):
                break
            self.send('storage write ' + filename_to +  ' ' + str(len(filedata)) + '\r')
            self.read.until(self.CLI_EOL)
            self.port.write(filedata)
            self.read.until(self.CLI_PROMPT)
            print(str(round(file.tell() / filesize * 100)) + '%')
        file.close()

    def read_file(self, filename):
        self.send('storage read ' + filename + '\r')
        self.read.until(self.CLI_EOL)
        size = self.read.until(self.CLI_EOL)
        size = int(size.split(b': ')[1])
        filedata = self.port.read(size)
        self.read.until(self.CLI_PROMPT)
        return filedata

    def receive_file(self, filename_from, filename_to):
        file = open(filename_to, 'wb')
        file.write(self.read_file(filename_from))
        file.close()

file = FlipperStorage('COM16')
file.start()
file.send_file('test.file', '/ext/test.file')
file.receive_file('/ext/test.file', 'test2.file')

# if(filecmp.cmp('test.file', 'test2.file', False)):
#     print('OK')
# else:
#     print('Error')
#os.remove("test2.file")

file.list_tree()
file.stop()