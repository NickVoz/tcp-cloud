import os
import socket, time, random, sys, string

ROOT_FOLDER = os.getcwd()
USERS = dict()  # dictionary representing amount of computers connected on every UID
USERS_UPDATE = dict()


def receiveFiles(changePath, clientFile):
    # first line sent is the size of the file, will be used as iteration
    # parameter in a loop
    fileSize = int(clientFile.readline())
    relPath = os.path.dirname(changePath)
    # Creates the received files and directories
    os.makedirs(relPath, exist_ok=True)
    with open(changePath, 'wb') as f:
        while (fileSize > 0):
            data = clientFile.read(min(2048, fileSize))
            f.write(data)
            fileSize -= len(data)
        # writes an empty byte in case file is empty
        if fileSize == 0:
            f.write(b'')


def main(portNum):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', portNum))
    s.listen(10)
    while True:
        clientSocket, clientAddress = s.accept()
        with clientSocket, clientSocket.makefile('rb') as clientFile:
            userQuery = clientFile.readline().strip()
            if userQuery == b'':
                continue
            # Transmission beginning - checks if client is a new client,
            # allocates a new UID to this user and sends it to him
            if userQuery == b'UID_REQ':
                clientID = generateUID()
                clientSocket.send(clientID)
                print(clientID.decode('utf-8'))
                USERS[clientID.decode('utf-8')] = 0
                USERS_UPDATE[clientID.decode('utf-8')] = dict()
                userFolder = os.path.join(ROOT_FOLDER, clientID.decode('utf-8'))
                os.mkdir(userFolder)
                continue
            # send contents of locally saved user file to user
            elif userQuery == b'UID_NUM':
                clientID = clientFile.readline().strip()  # receives UID
                userFolder = os.path.join(ROOT_FOLDER, clientID.decode('utf-8'))
                USERS[clientID.decode('utf-8')] += 1
                # send user's unique sub-serial number
                clientSocket.send(str(USERS[clientID.decode('utf-8')]).encode('utf-8') + b'\n')
                sendInitFiles(clientSocket, userFolder, clientID.decode('utf-8'))
                continue

            # due to the limited amount of updates each  cycle for the client, the program will enter this loop
            # a limited amount of times
            while userQuery == b'DELETION' or userQuery == b'MODIFICATION':
                fileType = clientFile.readline().strip() # gets info whether given path is a file or folder
                clientID = clientFile.readline().strip().decode()
                subID = int(clientFile.readline().strip().decode())  # strips to str
                relPath = clientFile.readline().strip().decode()
                # updates the list of clients waiting for an update
                updatePending = [i for i in range(0, subID)] + [i for i in range(subID + 1, USERS[clientID] + 1)]
                if userQuery == b'DELETION':
                    deleteFile(relPath)
                    if updatePending != []:
                        USERS_UPDATE[clientID][(relPath, "DELETION")] = updatePending
                elif userQuery == b'MODIFICATION':
                    if fileType == b'DIR':
                        os.makedirs(os.path.join(ROOT_FOLDER, clientID, relPath), exist_ok=True)
                    else:
                        # the client is going to transmit changes to the server, write the received modified file.
                        recvPath = os.path.join(ROOT_FOLDER, clientID, relPath)
                        receiveFiles(recvPath, clientFile)
                    if updatePending != [] :
                        USERS_UPDATE[clientID][(relPath, "MODIFICATION")] = updatePending
                userQuery = clientFile.readline().strip()  # updates user query

            # user is already initialized, sends his UID
            if userQuery == b'UPDATE_REQ':
                clientID = clientFile.readline().strip().decode('utf-8')  # receives UID
                subID = int(clientFile.readline().strip().decode('utf-8'))
                userChanges = USERS_UPDATE[clientID]  # get sub dictionary with specified users' changes
                # iterate over keys and check if connected clinet is in the current change
                for item in userChanges:
                    # check if the user's sub ID is in the update list for the current event
                    if userChanges[item] is not None and subID in userChanges[item]:
                        # checks if file was deleted or changed
                        if item[1] == "DELETION":
                            clientSocket.send(b'DELETION' + b'\n')
                            clientSocket.send(item[0].encode() + b'\n')
                            USERS_UPDATE[clientID][item].remove(subID)
                        elif item[1] == "MODIFICATION":
                            clientSocket.send(b'MODIFICATION' + b'\n')
                            sendInitFiles(clientSocket, item[0], clientID)
                            USERS_UPDATE[clientID][item].remove(subID)
            clientSocket.close()


def generateUID():
    output = str()
    for i in range(128):
        result = random.randint(0, 1)
        # appends a random letter if result is 0
        if result == 0:
            output += string.ascii_lowercase[random.randint(0, len(string.ascii_lowercase) - 1)]
        else:
            output += str(random.randint(0, 9))
    return bytes(output, "utf-8")


def sendInitFiles(clientSocket, dir, clientID):
    """
     sends the user's files when an existing user logs in with a new session
    """
    # loop iterates over tuple of the all the files in the subdirectories
    for path, directories, files in os.walk(dir):
        if files == []:
            relPath = bytes(os.path.relpath(path, clientID), 'utf-8')
            clientSocket.sendall(relPath + b'\n' + b'\n')
        for file in files:
            # full file path for reading and sending data
            fullPath = os.path.join(path, file)
            # relative path for creating an identically named path
            # for the client
            relPath = bytes(os.path.relpath(path, clientID), 'utf-8')
            if relPath == b'.': relPath = b''
            # transmission size - for sending loop purposes.
            # when the other side gets data with size identical
            # to the size received, moves on to receive next file
            size = os.path.getsize(fullPath)

            with open(fullPath, 'rb') as f:
                clientSocket.sendall(relPath + b'\n')  # send relative path
                clientSocket.sendall(bytes(file, 'utf-8') + b'\n')  # filename

                # sends the file size - used for writing data to file on receiving side
                clientSocket.sendall(bytes(str(size), 'utf-8') + b'\n')
                data = f.read(2048)
                # Inner loop iterating over file contents, sends 2048 bytes of data each time
                while data != b'':
                    clientSocket.send(data)
                    data = f.read(2048)

def sendFile(clientSocket, filePath, clientID):
    fileDir= os.path.dirname(filePath)
    fullFilePath = os.path.join(ROOT_FOLDER, clientID, filePath)
    clientSocket.send(os.path.relpath(filePath, fileDir).encode('utf-8') + b'\n') # sends file name
    size = os.path.getsize(fullFilePath)
    if os.path.isdir(fullFilePath):
        clientSocket.send(filePath.encode('utf-8') + b'\n')
        clientSocket.send(b'\n')
        return
    with open(fullFilePath, 'rb') as f:
        # sends the file size - used for writing data to file on receiving side
        clientSocket.sendall(bytes(str(size), 'utf-8') + b'\n')
        data = f.read(2048)
        # Inner loop iterating over file contents, sends 2048 bytes of data each time
        while data != b'':
            clientSocket.send(data)
            data = f.read(2048)



def deleteFile(path):
    """
    This function recursively deletes a given directory or file, handles errors as well
    """
    if os.path.isdir(path):
        try:
            os.rmdir(path)
        except OSError:  # directory not empty
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


if __name__ == "__main__":
    # first argument indicates listening port number
    if not sys.argv[1].isdigit():
        raise Exception("Invalid port number")
    main(int(sys.argv[1]))
