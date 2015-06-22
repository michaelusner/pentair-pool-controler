import serial


def to_int(x):
    return int(x, 16)


class PentairCom(object):
    Equip1 = 8
    Equip2 = 9
    WaterTemp = 20
    AirTemp = 24

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

    def read_status(self):
        while True:
            packet = self.get_packet()
            if len(packet) == 0:
                continue
            if 89 in packet or 95 in packet:
                print packet
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
                if src == self.Ctrl.MAIN and dst == self.Ctrl.BROADCAST:
                    equip1 = "{0:08b}".format(packet[self.Equip1])
                    equip2 = "{0:08b}".format(packet[self.Equip2])
                    # print "Source:        {0}".format(src_controller)
                    # print "Destination:   {0}".format(dst_controller)
                    print "Pool:          {0}".format(equip1[2:3])
                    print "Spa:           {0}".format(equip1[7:8])
                    print "Air Blower:    {0}".format(equip1[5:6])
                    print "Pool Light:    {0}".format(equip1[3:4])
                    print "Spa Light:     {0}".format(equip1[4:5])
                    print "Cleaner:       {0}".format(equip1[6:7])
                    print "Water Feature: {0}".format(equip1[1:2])
                    print "Aux:           {0}".format(equip2[7:8])
                    if len(packet) >= self.WaterTemp:
                        print "Water Temp:    {0}".format(packet[self.WaterTemp])
                    if len(packet) >= self.AirTemp:
                        print "Air Temp:      {0}".format(packet[self.AirTemp])


if __name__ == "__main__":
    x = PentairCom('com6')
    x.read_status()
