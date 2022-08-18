import signal
import sys
import socket
import libvirt
from time import sleep
from xml.dom import minidom

def sigint_handler(sig,frame):
    global conn
    global tcpServer
    global doms
    print("Closing AutoScaler")
    if conn is None:
        exit(0)
    else:
        for i in range(len(doms)):
            if i != 0 and doms[i].isActive():
                dom.shutdown()
        
        conn.close()
        if tcpServer is None:
            exit(0)
        else:
            tcpServer.close()
            exit(0)

def findIps():
    global hosts
    print('VM Names : ')
    for host in hosts:
        print(host.attributes['name'].value)
        if host.attributes['name'].value in domNames:
            domIps.append(host.attributes['ip'].value)


SCALER_IP = '127.0.0.3'
SCALER_PORT = 50000
THRESHOLD = 71
LOW_THRESHOLD = 30
domNames = ['vm1','vm2']
domIndex = 0
domIps = []
domPorts = [49950,49900]
doms = []
signal.signal(signal.SIGINT,sigint_handler)
conn = libvirt.open('qemu:///system')

if conn is None:
    print('Failed to open connection to qeumu')
    exit(1)
network = conn.networkLookupByName('default')
raw_xml = network.XMLDesc(0)
xml = minidom.parseString(raw_xml)
hosts = xml.getElementsByTagName('host')
# print(hosts)
findIps()

dom = conn.lookupByName(domNames[0])
if dom is None:
    print('Failed to find the domain '+ domNames[0])
    exit(1)

doms.append(dom)
if dom.isActive() == False:
    print('vm1 is not active')
    exit(1)

tcpServer = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
tcpServer.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    tcpServer.bind((SCALER_IP, SCALER_PORT))
except socket.error as e:
    print(str(e))

print('Autoscaler is running with I/P: ',SCALER_IP)
tcpServer.listen(5)

while True:
    (connectionObj,(client_ip,client_port)) = tcpServer.accept()
    with connectionObj:
        data = connectionObj.recv(32).decode('utf-8')
        print('Connection Received From Client with I/P :',client_ip)
        # ! inspect ip address from virsh of first vm
        if data == '1': # * send the first ip and port
            sleep(5) # ! need to remove this later
            ip = domIps[0]
            port = domPorts[0]
            data = bytes(f"ip:{ip},port:{port}",'utf-8')
            connectionObj.sendall(data)
            
            # * starting monitoring......
            th_count = 0
            th_low_count = 0
            print('Starting CPU Montiroing...........')
            while True:
                cpu1 = doms[0].getCPUStats(True)[0]['cpu_time']
                sleep(1)
                cpu2 =doms[0].getCPUStats(True)[0]['cpu_time']
                util = (cpu2 - cpu1) / (10 ** 7)
                print(util)
                if util > THRESHOLD:
                    th_count = th_count + 1
                    print("overload count : ,",th_count)
                else:
                    th_count = 0
                if th_count >= 5 :
                    # ! load a new vm
                    th_count = 0
                    domIndex = domIndex + 1
                    # print(domIndex)
                    if domIndex >= len(domNames):
                        continue
                    print("overload is more than 5 seconds\n Triggering new vm : " + domNames[domIndex])
                    dom = conn.lookupByName(domNames[domIndex])
                    if dom is None:
                        print('Failed to find the domain '+ domNames[domIndex])
                        exit(1)
                    doms.append(dom)
                    if dom.isActive() == False:
                        dom.create()
                    timeout =0 
                    while dom.isActive() == False:
                        timeout = timeout + 5
                        sleep(5)
                        if timeout >= 20:
                            print("TIMEOUT: vm is not activated after 20 secs")
                            exit(1)
                    
                    sleep(20)
                    ip = domIps[domIndex]
                    port = domPorts[domIndex]
                    data = bytes(f"ip:{ip},port:{port}",'utf-8')
                    connectionObj.sendall(data)
                if util <= LOW_THRESHOLD:
                    th_low_count = th_low_count + 1
                    print('Underload count: ',th_low_count)
                else:
                    th_low_count = 0
                if th_low_count >=5:
                    th_low_count = 0
                    if domIndex == 0:
                        continue
                    print("Underload is more than 5 seconds\n Stopping vm : " + domNames[domIndex])
                    while True:
                        if domIndex == 0:
                            break
                        if doms[domIndex].isActive():
                            doms[domIndex].shutdown()
                            print(f'{domNames[domIndex]} has been stopped')
                            doms.pop()
                            domIndex = domIndex - 1                            
                            sleep(5)
                            break
                        doms.pop()
                        domIndex = domIndex - 1
                    






#! close dom conn
conn.close()
tcpServer.close()