from time import sleep
import datetime

from docutils.parsers.rst import states
import serial


def to_int(x):
    return int(x, 16)


def bool_to_status(status):
    return "On" if int(status) else "Off"


class PentairCom(object):
    Equip1 = 8
    Equip2 = 9
    WaterTemp = 20
    AirTemp = 24
    Hour = 6
    Minute = 7

    class State:
        OFF = 0
        ON = 1

    class Ctrl:
        MAIN = 0x10
        REMOTE = 0x20
        PUMP1 = 0x60
        BROADCAST = 0x0f

    Controller = {
        Ctrl.MAIN: "Main",
        Ctrl.REMOTE: "Remote",
        Ctrl.PUMP1: "Pump1",
        Ctrl.BROADCAST: "Broadcast"
    }

    class Feature:
        SPA = 1
        CLEANER = 2
        AIR_BLOWER = 3
        SPA_LIGHT = 4
        POOL_LIGHT = 5
        WATER_FEATURE = 7
        SPILLWAY = 8
        AUX = 9

    def __init__(self, com):
        self.com = com
        self.port = serial.Serial(com, 9600)

    def __del__(self):
        self.port.close()

    def get_packet(self):
        header = [0, 0, 0, 0]
        while header != [255, 0, 255, 165]:
            data = ord(self.port.read())
            header = header[1:] + [data]
        # build up the packet
        packet = [165, ]
        packet += [ord(x) for x in self.port.read(5)]
        packet += [ord(x) for x in self.port.read(packet[-1])]
        checksum = (ord(self.port.read()) * 256) + ord(self.port.read())
        packet_checksum = sum(packet)
        if packet_checksum != checksum:
            print "Checksum is bad: got {0} and calculated {1}".format(checksum, packet_checksum)
            return []
        return packet

    def send_command(self, feature, state):
        header = [0x00, 0xff]
        packet = [165, 31, self.Ctrl.MAIN, self.Ctrl.REMOTE, 134, 2, feature, 1 if state else 0]
        checksum = sum(packet)
        packet.append(checksum / 256)
        packet.append(checksum % 256)
        print "Sending {0}".format(header + packet)
        self.port.write(header + packet)

    def read_status(self):
        packet = []
        while len(packet) == 0:
            packet = self.get_packet()
        dst = packet[2]
        if dst in self.Controller:
            dst_controller = self.Controller[dst]
        else:
            dst_controller = dst
        src = packet[3]
        if src in self.Controller:
            src_controller = self.Controller[src]
        else:
            src_controller = src
        data_length = packet[5]
        if data_length > 1:
            print "Source:        {0}".format(src_controller)
            print "Destination:   {0}".format(dst_controller)
            print packet
            print
            if src == self.Ctrl.MAIN and dst == self.Ctrl.BROADCAST:
                equip1 = "{0:08b}".format(packet[self.Equip1])
                equip2 = "{0:08b}".format(packet[self.Equip2])
                # print "Source:        {0}".format(src_controller)
                # print "Destination:   {0}".format(dst_controller)
                print "Time:          {0:02d}:{1:02d}".format(packet[self.Hour], packet[self.Minute])
                print "Pool:          {0}".format(bool_to_status(equip1[2:3]))
                print "Spa:           {0}".format(bool_to_status(equip1[7:8]))
                print "Air Blower:    {0}".format(bool_to_status(equip1[5:6]))
                print "Pool Light:    {0}".format(bool_to_status(equip1[3:4]))
                print "Spa Light:     {0}".format(bool_to_status(equip1[4:5]))
                print "Cleaner:       {0}".format(bool_to_status(equip1[6:7]))
                print "Water Feature: {0}".format(bool_to_status(equip1[1:2]))
                print "Aux:           {0}".format(bool_to_status(equip2[7:8]))
                if len(packet) >= self.WaterTemp:
                    print "Water Temp:    {0}".format(packet[self.WaterTemp])
                if len(packet) >= self.AirTemp:
                    print "Air Temp:      {0}".format(packet[self.AirTemp])
                print

if __name__ == "__main__":
    x = PentairCom('com6')
    state = True
    while True:
        x.read_status()
        if datetime.datetime.now().second % 5 == 0:
            send_state = x.State.ON if state else x.State.OFF
            x.send_command(x.Feature.POOL_LIGHT, send_state)
            state ^= True
        sleep(1)
