# tcp-cloud

Python scripts for a cloud server and clients, supports multiple connections for a single client and serving multiple clients simultaneously.

### Running the program

**1. Prerequisites:**
  - The `watchdog` library, which can be installed using `pip install watchdog`
  - IP address and desired listening port for the server machine using `ip a` or `ifconfig` on Linux, or `ipconfig` on Windows.

**2. Executing the program:**
  - First, run `python server.py port` to initialize the server.
    - `port` being the port number.
    - **Example:** `python server.py 12345` will make the server listen to port 12345.
  - Now, every client can be initialized using `python client.py ipaddr, port, filepath, interval, UID`.
    - `ipaddr` is the server's address.
    - `port` is the server's listening port.
    - `filepath` is the path to the desired file.
    - `interval` is the desired update request interval against the server.
    - `UID` is an optional argument which can be used to initialize additional clients for a single user.
    - If a UID was not entered by the user, a 128 characters long UID for this specific client will be created and displayed on the client's terminal.
    - **Example:** `python client.py 127.0.0.1 12345 ~/folder` will initialize the client with a server thtat's listening to port 12345 at address 127.0.0.1, and copy all the contents of folder to the server.

  Both programs will keep running in the background, the server will continue accepting additional clients, while the client will periodically check for updates in the destination folder.
