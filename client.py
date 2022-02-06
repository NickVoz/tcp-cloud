import socket, time, random, sys, os
import watchdog.observers
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent

READ_SIZE = 2048


class ClientDetails:
    def __init__(self):
        self.ipAddr = 0
        self.portNum = 0
        self.path = None
        self.UID = str()
        self.subID = 0
        self.socket = None


client = ClientDetails()


class EventHandler(FileSystemEventHandler):
    def on_any_event(self, event):

        client.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.socket.connect((client.ipAddr, client.portNum))
        # opens a socket to transmit changes
        if event.is_directory and event.event_type == 'modified':  # we want to send only file deletions.
            return None
        # server will delete it's copy of the user's data and will update all other clinet instances with deletion
        # of the specified folder
        eventPath = os.path.relpath(event.src_path, client.path)
        if event.event_type == 'deleted':
            time.sleep(0.5)
            if os.path.isdir(event.src_path):
                typeOfFile = b'DIR'
            elif os.path.isfile(event.src_path):
                typeOfFile = b'FILE'
            else:
                return
            client.socket.send(b'DELETION' + b'\n')
            # send identifying data
            client.socket.send(typeOfFile + b'\n')
            client.socket.send(client.UID.encode('utf-8') + b'\n')  # send UID
            client.socket.send(str(client.sub_ID).encode('utf-8') + b'\n')  # send sub ID
            client.socket.send(eventPath.encode('utf-8') + b'\n')  # send path

        # event is either a folder creation or file modification -server deletes file and client uploads a new copy
        elif event.event_type == 'modified' or event.event_type == 'created':
            time.sleep(0.5)
            if os.path.isdir(event.src_path):
                typeOfFile = b'DIR'
            elif os.path.isfile(event.src_path):
                typeOfFile = b'FILE'
            else:
                return
            client.socket.send(b'MODIFICATION' + b'\n')
            # send identifying data
            client.socket.send(typeOfFile + b'\n')
            client.socket.send(client.UID.encode('utf-8') + b'\n')  # UID
            client.socket.send(str(client.sub_ID).encode('utf-8') + b'\n')  # sub ID
            client.socket.send(eventPath.encode('utf-8') + b'\n')  # send path
            if event.is_directory == False:
                sendFile(eventPath)
        client.socket.close()


class Watcher:
    def __init__(self, interval, dir=".", handler=EventHandler()):
        self.observer = watchdog.observers.Observer()
        self.handler = handler
        self.interval = interval  # integer
        self.dir = dir

    def run(self):
        # start the observer
        self.observer.schedule(self.handler, self.dir, recursive=True)
        self.observer.start()
        runtime = time.time() + self.interval
        # the watcher object will run until the next update interval from the server arrives.
        while runtime > time.time():
            time.sleep(1)
        self.observer.stop()


def main(ipAddr, portNum, path, interval, UID=None):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)
    client.ipAddr = ipAddr
    client.portNum = int(portNum)
    client.path = path
    client.UID = UID
    global init
    init = False
    while True:
        client.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.socket.connect((ipAddr, int(portNum)))
        # initialization conditions
        # Program started without UID field - receive UID from server
        if client.UID is None:
            init = True
            client.socket.send(b'UID_REQ' + b'\n')
            client.UID = client.socket.recv(READ_SIZE).strip().decode('utf-8')
            client.sub_ID = 0
            client.socket.close()  # closes old socket
            continue
        # Program was started with existing UID, but not initialized
        elif client.UID is not None and init == False:
            init = True
            client.socket.send(b'UID_NUM' + b'\n')
            client.UID = UID
            # sends UID to the server
            client.socket.send(UID.encode('utf-8') + b'\n')
            client.sub_ID = dlFiles(client.socket, path)
            client.socket.close()  # closes old socket
            continue

        while True:

            # Program is initialized now - monitor changes and send periodic requests to sync data from the server
            w = Watcher(int(interval), client.path, EventHandler())
            w.run()

            client.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.socket.connect((ipAddr, int(portNum)))

            # Watcher ran while desired interval occurred, send an update request from the server
            client.socket.send(b'UPDATE_REQ' + b'\n')
            client.socket.send(client.UID.encode('utf-8') + b'\n')
            client.socket.send(str(client.sub_ID).encode('utf-8') + b'\n')
            with client.socket, client.socket.makefile('rb') as recvFile:
                while True:
                    param = recvFile.readline().strip()
                    if param == b'':
                        break
                    fileName = recvFile.readline().strip().decode()
                    if param == b'DELETION':
                        deleteFile(fileName)
                    elif param == b'MODIFICATION':
                        dlFiles(client.socket, fileName)

def dlFiles(s, path):
    with s.makefile('rb') as recvFile:
        subID = recvFile.readline().strip().decode()
        while True:
            desiredPath = recvFile.readline().strip().decode()

            fileName = recvFile.readline().strip().decode()
            # check if file transmission ended
            if fileName == '' and desiredPath != '':
                os.makedirs(os.path.join(path, desiredPath), exist_ok=True)
                continue
            elif fileName == '' and desiredPath == '':
                break
            # second line sent is the size of the file, will be used as iteration
            # parameter in a loop
            fileSize = int(recvFile.readline())
            currPath = os.path.join(path, desiredPath)
            # Creates the received files and directories
            os.makedirs(currPath, exist_ok=True)
            with open(os.path.join(currPath, fileName), 'wb') as f:
                while (fileSize > 0):
                    data = recvFile.read(min(2048, fileSize))
                    f.write(data)
                    fileSize -= len(data)
                # writes an empty byte in case file is empty
                if fileSize == 0:
                    f.write(b'')
    return subID


def sendFile(path):
    fullPath = os.path.join(client.path, path)
    size = os.path.getsize(fullPath)
    with open(fullPath, 'rb') as f:
        # sends the file size - used for writing data to file on receiving side
        client.socket.sendall(bytes(str(size), 'utf-8') + b'\n')  # send file size
        data = f.read(2048)
        # Inner loop iterating over file contents, sends 2048 bytes of data each time
        while data != b'':
            client.socket.send(data)
            data = f.read(2048)


def deleteFile(path):
    """
    This function recursively deletes a given directory or file, handles errors as well
    """
    if os.path.isdir(path):
        try:
            os.rmdir(path)
        except OSError:
            for i in os.listdir(path):
                subFile = os.path.join(path, i)
                deleteFile(subFile)
            # directory is now empty
            os.rmdir(path)
        except FileNotFoundError:
            pass
    # file is not a directory
    else:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


# argv[1] - IP address, argv[2] - port, argv[3] - file path
# argv[4] - request interval, argv[5] - optional UID
if __name__ == "__main__":
    # check inputs
    if len(sys.argv[1].split('.')) != 4:
        raise Exception("Invalid IP Address")
    if not sys.argv[2].isdigit():
        raise Exception("Invalid Port number")
    if not sys.argv[4].isdigit():
        raise Exception("Invalid interval value")
    # no UID was given - initialize main() with new UID value
    if len(sys.argv) != 6:
        main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
