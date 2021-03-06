import socket
import sys
import atexit
from command import Command
from threading import Thread
from util.bytebuffer import ByteBuffer
from config import IP, PORT, BUFFER, NAME


class RobotClient:
    socket = None
    connected = False
    server_address = (IP, PORT)
    packet_number = 0
    read_thread = None
    on_command = None

    def __init__(self, on_command):
        """

        :type on_command: function
        """
        if not callable(on_command):
            print 'Invalid function passed, please pass a function to on_command'
            sys.exit()

        self.on_command = on_command

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except socket.error:
            print 'Failed to create socket'
            sys.exit()

    def connect(self):
        """
        Connect to server and send a session packet
        Listening is handled on a separate thread
        :return:
        """
        # self.socket.connect(self.server_address)

        self.connected = True

        self.read_thread = Thread(target=self.start_reading)
        self.read_thread.start()

        self.send_session_packet()

        atexit.register(self.disconnect)

    def disconnect(self):
        """
        Disconnect from the server
        :return:
        """
        self.connected = False

        self.socket.shutdown(socket.SHUT_WR)

    def send_session_packet(self):
        """
        Send a session packet to the server to start a new session
        :return:
        """
        arr = bytearray([0x00, 0, len(NAME)])
        arr.extend(NAME)

        self.socket.sendto(arr, self.server_address)

    def send_info_packet(self, motor1, motor2, motor3, motor4, acc, gyro, compass):
        """
        Send a Sensor Information Packet to the server
        :param motor1: The current power of motor1
        :param motor2: The current power of motor2
        :param motor3: The current power of motor3
        :param motor4: The current power of motor4
        :param acc: A Vector3 of the current acceleration of the robot
        :param gyro: A Quaternion that represents the current orientation of the robot
        :param compass: A Vector3 of the current compass of the robot
        :return:
        """
        total_size = 64

        accX, accY, accZ = acc
        gyroX, gyroY, gyroZ, gyroW = gyro
        compassX, compassY, compassZ = compass

        array = bytearray([0] * total_size)
        buf = ByteBuffer(array, 0, total_size)

        buf.put_SLInt64(self.packet_number)
        buf.put_SLInt32(motor1)
        buf.put_SLInt32(motor2)
        buf.put_SLInt32(motor3)
        buf.put_SLInt32(motor4)
        buf.put_LFloat32(accX)
        buf.put_LFloat32(accY)
        buf.put_LFloat32(accZ)
        buf.put_LFloat32(compassX)
        buf.put_LFloat32(compassY)
        buf.put_LFloat32(compassZ)
        buf.put_LFloat32(gyroX)
        buf.put_LFloat32(gyroY)
        buf.put_LFloat32(gyroZ)
        buf.put_LFloat32(gyroW)

        to_send = bytearray([0] * (total_size + 1))
        to_send[0] = 0x02
        buf.set_position(0)
        buf.get(to_send, 1, total_size)

        self.socket.sendto(to_send, self.server_address)

    def start_reading(self):
        """
        Begin reading data from the server

        SHOULD ONLY BE DONE BY self.connect()
        :return:
        """
        while self.connected:
            print "Waiting for command.."

            # Wait until we get a UDP packet
            data, adr = self.socket.recvfrom(BUFFER)

            # Convert to byte array
            barr = bytearray(data)

            if barr[0] == 0x03:
                # If the opcode is 0x03, then we got a command
                print("Got Motor Command")

                # Extract the rest of the packet
                buf = ByteBuffer(barr, 1, 24)

                pnum = buf.get_SLInt64()

                if pnum < self.packet_number:
                    continue # Ignore this packet, we got a packet with a higher number
                else:
                    self.packet_number = pnum # Update the latest packet number with the one in this packet

                # Get the value of each motor
                motor1 = buf.get_SLInt32()
                motor2 = buf.get_SLInt32()
                motor3 = buf.get_SLInt32()
                motor4 = buf.get_SLInt32()

                # Convert to motor command
                command = Command(motor1, motor2, motor3, motor4)

                # Invoke on_command callback
                self.on_command(command)
            else:
                print("Unknown packet:\nOpCode: " + barr[0] + "\nData:" + data)
