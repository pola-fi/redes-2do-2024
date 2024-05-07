import socket
from lib.message import UploadConnectionMessage
from lib.message import ConnectionDownloadMessage
from lib.message import ResponseUploadMessage
from lib.message import StartDownloadMessage
from lib.message import UploadMessage
from lib.encoder import Encoder
from lib.command import Command
from lib.window import Window
from lib.file import File
import time
import os
import select
import threading
from lib.utilities.socket import send_msg
from lib.utilities.socket import receive_msg

CHUNK_SIZE = 5000
NUMBER_OF_BYTES_RECEIVED = 10000
TIMEOUT = 1
DIRECTORY_PATH = '/files/client'
SELECTIVE_REPEAT_COUNT = 5

class Client:
    def __init__(self, server_host, server_port):
        self.server_host = server_host
        self.server_port = server_port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self):
        self.socket.close()

    ## UPLOAD

    def open_upload_conection(self, file: File):
    
        message = UploadConnectionMessage(file.name, file.get_size())
        print(f"Sending ConectionMessage for file:{file.name} with size:{file.get_size()}")

        send_msg(self.socket, message, self.server_host, self.server_port)
    
        received_msg, server_address = receive_msg(self.socket)

        if received_msg['command'] == Command.RESPONSE_CONNECTION:
            self.server_port = received_msg['server_port']
            print(f"On Server address: {server_address},assigned port: {self.server_port}")

    def upload_file(self, file: File):
        ## Espera para que el server este escuchando
        time.sleep(1)

        # para silumar una perdida de paquete
        number_of_packet = 1
        offset = 0

        with open(file.absolute_path, 'rb') as open_file:
            while True:
                open_file.seek(offset)
                chunk = open_file.read(CHUNK_SIZE)
                if not chunk:
                    break
                
                message = UploadMessage(chunk.decode(),offset)
                # TODO: Simula la perdida de un paquete cada 5
                if number_of_packet % 5 != 0 :
                    send_msg(self.socket, message, self.server_host, self.server_port)

                chunk_size = len(chunk)
                offset = self.handle_recive_message(offset, chunk_size)

                print(f"offset:{offset},chunk size:{chunk_size}")
                    
                number_of_packet += 1

    def handle_recive_message(self, offset, chunk_size):
        try:
            ready = select.select([self.socket], [], [], TIMEOUT)
            if ready[0]:
                response_message, _ = receive_msg(self.socket)

                if response_message['file_offset'] == offset:
                    offset += chunk_size
            else:
                # El temporizador ha expirado, no se recibió ninguna respuesta
                print(f"Time out after {TIMEOUT} seconds")
        
            return offset
        
        except socket.timeout:
            # El temporizador ha expirado, no se recibió ninguna respuesta
            print("Sever Time out")
 
    ## Selective Upload


    ## Download

    def download_open_conection(self,file: File):
        message = ConnectionDownloadMessage(file.name)

        send_msg(self.socket, message, self.server_host, self.server_port)
        response_message, server_address = receive_msg(self.socket)
    
        if response_message['command'] == Command.RESPONSE_DOWNLOAD_CONECTION:
            response_port = response_message['server_port']
            file_size = response_message['file_size']
            print(f"Server address: {server_address},responded with port: {response_port}")
            
            message = StartDownloadMessage()
            send_msg(self.socket, message, self.server_host, self.server_port)

            self.socket.close()
            self.server_port = response_port
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.server_host, self.server_port))
            print(f"Connection started on host:{self.server_host}, on port:{self.server_port}")

            return file_size

    def download_file(self, file: File, file_size_to_download):

        # Simula la perdida de un paquete
        number_of_packet = 1

        file.create()
        
        while file.get_size() < file_size_to_download:
            response_message, server_address = receive_msg(self.socket)
            if (response_message['command'] == Command.DOWNLOAD):

                data = response_message['file_data']
                offset = response_message['file_offset']

                print(f"Recibed data with offset:{offset}")
                file.write(data, offset)
                self.handle_send_ack(offset, server_address, number_of_packet)

                number_of_packet += 1        

    #TODO: Vuela, con la perdida de paquetas, queda solo el envio 
    def handle_send_ack(self, offset, client_address, number_of_packet):

        #prueba para simular perdida de paquete cada 6
        print(f"number of packet {number_of_packet}")
        if number_of_packet % 6 != 0 :
            message = ResponseUploadMessage(offset)
            send_msg(self.socket, message, client_address[0], client_address[1])
        else:
            print("no se envia este ACK")

    ## Selective Download

    def write_to_socket(self):

        with open(self.file.absolute_path, 'rb') as open_file:
            while True:
                if self.window.has_space():
                    print(f"chunk number sent: {self.window.next_sent_element() / self.window.chunk_size}, offset: {self.window.next_sent_element()}")
                    print(f"next offset: {self.window.next_sent_element()}")
                    open_file.seek(self.window.next_sent_element())
                    chunk = open_file.read(CHUNK_SIZE)
                    if not chunk:
                        print("no hay chunk")
                        break
                    
                    message = UploadMessage(chunk.decode(), self.window.next_sent_element())
                    #print(f"Sent chunk message:{message.toJson()}, to host:{self.server_host}, on port:{self.server_port}")
                    # TODO: Simula la perdida de un paquete cada 100, quitar
                    #if chunk_number % 100 != 0 :

                    self.window.add(self.window.next_sent_element())
                    self.socket.sendto(Encoder().encode(message.toJson()), (self.server_host, self.server_port))
                    self.window.last_sended = self.window.next_sent_element()
                
                    #self.offset =+ CHUNK_OF_BYTES_READ
                else: 
                    print(f"windows dont have space")
                    time.sleep(1)

    def read_of_socket(self):
        while True:
            if self.window.has_space():
                print(f"window size before receiving: {self.window.size()}")
                response, _ = self.socket.recvfrom(1024)
                response_decoded = Encoder().decode(response.decode())
                response_offset = int(response_decoded['file_offset'])
                print(f"recived chunk number:{response_offset / CHUNK_OF_BYTES_READ}, offset:{response_offset}")
                if self.window.is_first(response_offset):
                    self.window.remove_first()
                    self.window.last_received = response_offset
                else: 
                    self.window.remove_all()
            else:
                print(f"windows dont have space")
                #print(f"window size: {self.window.size()}")

    def upload_with_selective_repeat(self, file: File):
        time.sleep(1)
        self.file = file
        self.number_chunk_for_send = SELECTIVE_REPEAT_COUNT
        self.window = Window(SELECTIVE_REPEAT_COUNT, CHUNK_OF_BYTES_READ)

        escribir_thread = threading.Thread(target=self.write_to_socket)
        leer_thread = threading.Thread(target=self.read_of_socket)
        escribir_thread.start()
        leer_thread.start()
        escribir_thread.join()
        leer_thread.join()
        
            #while True:

                
                # self.socket.settimeout(TIMEOUT)

                # print("pase a recibir ack")
                # print(f"hay algo en la ventana?:{not window.is_empty()}")
                # print()
                # while not window.is_empty():
                #     try:
                #         if window.has_space():
                #             response, _ = self.socket.recvfrom(1024)
                #             response_decoded = Encoder().decode(response.decode())
                #             response_offset = int(response_decoded['file_offset'])
                #             print(f"recived chunk number:{response_offset / CHUNK_OF_BYTES_READ}")
                #             if response_offset == offset:
                #                 offset += len(chunk)
                #                 print(f"offset old:{offset}")
                            
                #     except socket.timeout:
                #         break


                    # try:
                    #     ready = select.select([self.socket], [], [], TIMEOUT)
                    #     if ready[0]:
                    #         response, _ = self.socket.recvfrom(1024)
                    #         response_decoded = Encoder().decode(response.decode())
                    #         response_offset = response_decoded['file_offset']
                    #         if response_offset == offset:
                    #             offset += len(chunk)
                    #     else:
                    #         # El temporizador ha expirado, no se recibió ninguna respuesta
                    #         print("No se recibió respuesta del servidor dentro del tiempo de espera.")
                
                    # except socket.timeout:
                    #     # El temporizador ha expirado, no se recibió ninguna respuesta
                    #     print("No se recibió respuesta del servidor dentro del tiempo de espera.")

                    
                    # offset = self.handle_recive_message(offset, chunk)
                # print(f"offset:{offset},chunk_{len(chunk)}")
                        
                    
        

    

    
        
    
    


    
