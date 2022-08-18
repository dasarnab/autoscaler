import socket 
from threading import Thread,Lock,Condition
from time import sleep
from random import randint,seed,random


# host = '127.0.0.1'
# port = 49950
# BUFFER_SIZE = 2000 
# MESSAGE = input("tcpClientA: Enter message/ Enter exit:") 
seed(42)
# print(__name__)
PERFORMACE = False
req_generated = 0
req_generated_lock = Lock()
req_served = 0
req_served_lock = Lock() 
class AutoScaler(Thread):
    def __init__(self,ip,port): 
        Thread.__init__(self)
        self.ip = ip
        self.port = port
        self.servers = []
        self.init = -1
        self.connections = 0
        self.send_buffer = None
        self.recv_buffer = None
        # * need a lock b/w main thread and autoscaler
        self.lock = Lock()
        self.serverAvailable = Condition(self.lock)

    def run(self):
        autoscaler = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            autoscaler.connect((self.ip, self.port))
            self.init = 1
        except socket.error as e:
            print(e)
            self.init = 0
            return
        
        # * sendFirstIp
        self.send_buffer = b'1'
        autoscaler.sendall(self.send_buffer)

        while True:
            self.recv_buffer = autoscaler.recv(32).decode('utf-8')
            if not self.recv_buffer:
                break
            server_ip = self.recv_buffer.split(',')[0][3:]
            server_port = int(self.recv_buffer.split(',')[1][5:])

            # * ciritical section start
            self.lock.acquire()
            self.servers.append((server_ip,server_port))
            self.setConnectionns(self.getConnections() + 1)
            self.serverAvailable.notify()
            self.lock.release()
            
            
            # print(self.connections, self.servers)
        # self.servers.append((self.recv_buffer.))
        # ! must notify the main thread if it is sleeping
        self.lock.acquire()
        self.setConnectionns(-1)
        self.serverAvailable.notify()
        self.lock.release()


    def getConnections(self):
        return self.connections
    def setConnectionns(self,val):
        self.connections = val



class clientThread(Thread):

    def __init__(self,ip,port):
        Thread.__init__(self)
        self.ip = ip
        self.port = port
        self.lock = Lock()
        self.requests = []
        self.isStackEmpty = Condition(self.lock)
        self.init = -1

    def run(self):
        global PERFORMACE,req_served,req_served_lock
        print("Client Thread with ip : ",self.ip," ,port :",self.port)
        # * connection establish phase with server
        client_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_conn.connect((self.ip, self.port))
            self.init = 1
        except socket.error as e:
            print(e)
            self.init = 0
            exit()
        while True:
            self.lock.acquire()   
            while len(self.requests) == 0:
                self.isStackEmpty.wait()
            
            req_len,req_time = self.requests.pop()
            self.lock.release()
            if req_len == -1:
                break
            data = f"{req_len}"
            try:
                client_conn.sendall(bytes(data,'utf=8'))
                # print("req has been made with length: ",req_len)
                # sleep(req_time)
            except socket.error as e:
                print('send error: ',e)
                break
            try:
                recv_data = client_conn.recv(1).decode('utf-8')
            except socket.error as e:
                print('recv error: ',e)

            if PERFORMACE == True:
                req_served_lock.acquire()
                req_served = req_served + 1
                req_served_lock.release()

        client_conn.close()
        



class inputThread(Thread):

    def __init__(self):
        Thread.__init__(self)
        self.destroy = False

    def run(self):
        global delay_factor
        global PERFORMACE,req_generated,req_generated_lock,req_served,req_served_lock
        print('Input Thread is now active')
        while self.destroy == False:
            userInput = int(input()) #! Format => 1. inc load by 10% , 2. dec load by 10% 3. set load to
            if userInput == 1:
                print('inc load by 10%')
                delay_factor = (delay_factor - (0.1 * delay_factor))
            elif userInput == 2:
                print('dec load by 10%')
                delay_factor = (delay_factor + (0.1 * delay_factor))
            elif userInput == 3:
                loadval = float(input('Enter the new delay value: '))
                print(f'set load to {loadval}')
                delay_factor = loadval
            elif userInput == 4:
                print(f"Current Load is {delay_factor}")
            elif userInput == 5:
                PERFORMACE = True
                sleep(10)
                req_served_lock.acquire()
                PERFORMACE = False
                print('Throughput is', req_served // 10)
                req_served = 0
                req_served_lock.release()                
                req_generated_lock.acquire()
                print('Load in Reqests/Second is', req_generated // 10)
                req_generated = 0
                req_generated_lock.release()

            else:
                print('press 1 or 2 or 3 to increase/decrease/set the laod')



# while MESSAGE != 'exit':
#     tcpClientA.send(bytes(MESSAGE,'utf-8'))     
#     data = tcpClientA.recv(BUFFER_SIZE)
#     print(" Client2 received data:", data.decode('utf-8'))
#     MESSAGE = input("tcpClientA: Enter message to continue/ Enter exit:")

# tcpClientA.close() 

delay_factor = 3
if __name__ == '__main__':
    autoscaler = AutoScaler('127.0.0.3',50000)
    autoscaler.start()
    while autoscaler.init == -1:
        continue
    
    if autoscaler.init == 0 :
        autoscaler.join()
        print("exiting")
        exit()
    # * connection established with autoscaler 
    # * wait until connections become 1.
    server_connections = 0
    server_count = 0
    clientThreads = []
    activeClientThreads = 0
    ipThread = inputThread()
    ipThread.start()
    while True:
        # print("here")
        if not autoscaler.is_alive():
            print("Auto sclaer died")
            break
        autoscaler.lock.acquire()
        while(autoscaler.getConnections() == 0):
            # print("Sleeping")
            autoscaler.serverAvailable.wait()
        # print("woke up")
        # ! check this logic
        # ? what happens if connection decreases
        server_connections = autoscaler.getConnections()
        if server_connections == -1:
            autoscaler.lock.release()
            break
        new_conns = autoscaler.servers[server_count:server_connections]
        autoscaler.lock.release()
        # * now one server ip is avaulable to connect
        if server_connections == server_count:
            # * no new server has been added
            for i in  range(len(clientThreads)):
                if clientThreads[i] is None:
                    continue
                elif not clientThreads[i].is_alive():
                    print("reaping client thread ",i)
                    clientThreads[i].join()
                    clientThreads[i] = None
                    activeClientThreads = activeClientThreads - 1
                else:
                    # *generate a load and send that to this thread
                    clientThreads[i].lock.acquire()
                    # req_len = randint(2000,5000)
                    req_len = randint(1000,2000)
                    clientThreads[i].requests.append((req_len,1))
                    if len(clientThreads[i].requests) == 1:
                        clientThreads[i].isStackEmpty.notify()
                    clientThreads[i].lock.release()
            # * give a delay
            req_time = (delay_factor/ 500) * activeClientThreads
            if PERFORMACE == True:
                req_generated_lock.acquire()
                req_generated = req_generated + activeClientThreads
                # print('req: ',req_generated)
                req_generated_lock.release()
            sleep(req_time)
            

        else :
            # * new server has been added
            # * for all new added server create a client thread
            print('Adding new ips.....')
            for i in range(len(new_conns)):
                new_ip = new_conns[i][0]
                new_port = new_conns[i][1]
                # print(new_ip,new_port)
                newthread = clientThread(new_ip,new_port)
                newthread.start()
                clientThreads.append(newthread)
                activeClientThreads = activeClientThreads + 1

            print(f"Now using {activeClientThreads} servers")
            server_count = server_connections



    
    autoscaler.join()
    for th in clientThreads:
        if th is None:
            continue
        th.lock.acquire()
        th.requests.append((-1,0))
        if len(th.requests) == 1:
            th.isStackEmpty.notify()
        th.lock.release()
    
    for th in clientThreads:
        if th is not None:
            th.join()
    
    ipThread.destroy = True
    ipThread.join()
